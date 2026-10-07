# 180DATeam4

## Programs

- `tetris.py` — Tetris game built with Pygame.
- `hand_orientation.py` — Live MediaPipe hand-orientation display.

## Hand-orientation setup with Conda

Create a Conda environment with Python 3.11:

```bash
conda create --name tetris python=3.11 -y
conda activate tetris
```

Install the required packages inside the activated environment:

```bash
python -m pip install opencv-python mediapipe numpy
```

Run the orientation display from the project directory:

```bash
cd /Users/jiali/180DATeam4
python hand_orientation.py
```

The included hand model is loaded locally; the script does not download any
files. Hold one straight hand with all four fingertips aimed at the camera.
Pointer/index finger up and pinky down is `0 degrees`; clockwise rotation in
the displayed image is positive and counterclockwise rotation is negative.
Press `q` or Escape to quit.

You can adjust the pointing tolerance or select a different camera:

```bash
python hand_orientation.py --max-pointing-angle 25 --camera 1
```

When finished, leave the Conda environment with:

```bash
conda deactivate
```
