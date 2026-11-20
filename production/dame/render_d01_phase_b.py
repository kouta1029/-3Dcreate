"""Render the D01 production shots with Blender 4.3.2 and FFmpeg."""

import argparse
from pathlib import Path
from shutil import move
import subprocess
import sys
from time import perf_counter

import bpy

ROOT = Path(__file__).resolve().parent / "renders" / "d01"
SHOTS = {
    "V1": ("V1 | Interior turntable", 96, "V1.mp4"),
    "V2": ("03_cutaway_side", 1, "stills/V2_cutaway.png"),
    "V3": ("V3 | Macro approach", 72, "V3.mp4"),
    "V4_flat": ("V4 | Flat foil", 1, "stills/V4_flat.png"),
    "V4_crumpled": ("V4 | Crumpled foil", 1, "stills/V4_crumpled.png"),
}


def render_preview(scene, shot, frames, work_dir, percentage):
    scene.render.resolution_percentage = percentage
    for frame in frames:
        scene.frame_set(frame)
        scene.render.filepath = str(work_dir / f"{shot}_{frame:04}.png")
        started = perf_counter()
        bpy.ops.render.render(write_still=True)
        print(f"D01_PREVIEW {shot} {frame} {perf_counter()-started:.3f}", flush=True)


def render_v1_frames(scene, work_dir):
    # Only the lower assembly moves. Keep one full Eevee frame for the static
    # cabinet and render the changing region at the same pixel scale and samples.
    render = scene.render
    render.filepath = str(work_dir / "cavity.png")
    bpy.ops.render.render(write_still=True)
    render.use_border = render.use_crop_to_border = True
    render.border_min_y = .125
    render.border_max_y = .5625
    render.filepath = str(work_dir / "frame_")
    bpy.ops.render.render(animation=True)
    y = round((1-render.border_max_y) * render.resolution_y)
    return y


def encode_movie(shot, count, work_dir, destination, crop_top):
    frames = ["-framerate", "24", "-start_number", "1", "-i", str(work_dir / "frame_%04d.png")]
    command = ["ffmpeg", "-v", "error", "-y"]
    if shot == "V1":
        # Feather the edges over static pixels outside the rotating assembly.
        filters = (
            "[0:v]format=rgb24[cavity];"
            "[1:v]format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
            "a='255*min(1,min(Y,H-1-Y)/16)'[motion];"
            f"[cavity][motion]overlay=y={crop_top}:format=rgb:shortest=1,"
            "scale=out_color_matrix=bt709[out]"
        )
        command += ["-framerate", "24", "-loop", "1", "-i", str(work_dir / "cavity.png")]
        command += frames + ["-filter_complex_threads", "2", "-filter_complex", filters, "-map", "[out]"]
    else:
        command += frames + ["-vf", "scale=out_color_matrix=bt709"]
    staged = work_dir / destination.name
    subprocess.run(command + [
        "-frames:v", str(count), "-c:v", "libx264", "-preset", "medium", "-crf", "16",
        "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
        "-color_trc", "iec61966-2-1", "-movflags", "+faststart", "-threads", "2", str(staged),
    ], check=True)
    move(staged, destination)


def render_shot(scene, shot, count, destination, work_dir):
    destination.parent.mkdir(parents=True, exist_ok=True)
    scene.render.image_settings.compression = 10
    scene.render.resolution_percentage = 100
    scene.frame_set(1)
    started = perf_counter()
    crop_top = None
    if count == 1:
        scene.render.filepath = str(destination)
        bpy.ops.render.render(write_still=True)
    elif shot == "V1":
        crop_top = render_v1_frames(scene, work_dir)
    else:
        scene.render.filepath = str(work_dir / "frame_")
        bpy.ops.render.render(animation=True)
    rendered = perf_counter() - started
    encoded = 0.0
    if count > 1:
        started = perf_counter()
        encode_movie(shot, count, work_dir, destination, crop_top)
        encoded = perf_counter() - started
    print(f"D01_PHASE_B {shot} {count} {rendered/count:.3f} {rendered:.3f} {encoded:.3f}",
          flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("shot", choices=SHOTS)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--preview-frames", type=int, nargs="+")
    parser.add_argument("--preview-scale", type=int, choices=(50, 100), default=50)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    scene_name, count, relative_path = SHOTS[args.shot]
    scene = bpy.data.scenes[scene_name]
    bpy.context.window.scene = scene
    work_dir = args.work_dir.resolve() / args.shot
    work_dir.mkdir(parents=True, exist_ok=True)
    if args.preview_frames:
        if any(not 1 <= frame <= count for frame in args.preview_frames):
            parser.error(f"Preview frames for {args.shot} must be between 1 and {count}")
        render_preview(scene, args.shot, args.preview_frames, work_dir, args.preview_scale)
    else:
        render_shot(scene, args.shot, count, ROOT / relative_path, work_dir)


if __name__ == "__main__":
    main()
