# Video Explainer Agent

Generate educational explainer videos about **computer science and physics** using an AI-assisted content pipeline, narrated audio, and animated visuals.

The project combines a Python backend, LangGraph workflow orchestration, optional Gemini-powered writing and planning, text-to-speech narration, and video rendering. A web interface allows users to submit topics and track video-generation jobs.

> **Project status:** Active development. The CLI, backend workflow, Remotion renderer, and web interface are evolving. Some rendering paths and visual styles may have different levels of support depending on the topic.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [Environment Configuration](#environment-configuration)
- [Generate a Video from the CLI](#generate-a-video-from-the-cli)
- [Web Interface](#web-interface)
- [Video Rendering](#video-rendering)
- [Physics Animation Pipeline](#physics-animation-pipeline)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)

## Overview

Explaining a technical concept well requires more than generating a script. The explanation must be accurate, easy to follow, divided into meaningful scenes, narrated clearly, and accompanied by visuals that match what is being said.

Video Explainer Agent aims to automate that process.

Given a topic such as *binary search*, *CPU caches*, or *solar energy*, the system can research the topic, develop an explanation, evaluate and revise the script, plan scenes, generate narration, and render a video.

The project currently focuses on two subject areas:

- **Computer science:** algorithms, data structures, computer architecture, and related concepts.
- **Physics:** scientific principles and physical processes that benefit from clear explanations and visual demonstrations.

## Features

- **Research-backed explanations:** gathers supporting information, including from Wikipedia.
- **AI-assisted writing:** supports a deterministic scriptwriter and an optional Gemini-powered workflow.
- **Script evaluation and revision:** critiques the generated explanation and can revise it before approval.
- **Scene planning:** converts an explanation into structured scenes with visual descriptions and timing information.
- **Text-to-speech narration:** generates spoken narration for scenes.
- **Animated video rendering:** uses Remotion for React-based animations, with an FFmpeg rendering path also available.
- **Specialized physics animations:** includes a physics animation dispatcher and Manim-based scenes.
- **Web dashboard:** submits generation jobs and tracks their status.
- **Automated tests:** tests backend workflow logic and selected rendering and visual-planning behavior.

Feature availability can depend on the selected options, topic, installed dependencies, and external AI service availability.

## How It Works

A typical generation workflow follows these stages:

1. **Topic input** — receive the subject and selected generation options.
2. **Research** — gather relevant background information and evidence.
3. **Script generation** — produce an explanation using the deterministic writer or an optional Gemini-powered writer.
4. **Critique and revision** — evaluate the script and revise it when necessary.
5. **Scene planning** — divide the explanation into scenes and choose suitable visual representations.
6. **Narration** — generate audio for the planned scenes.
7. **Rendering** — combine narration and visuals into a video.
8. **Output** — save generated artifacts, including the final video when video rendering is enabled.

The exact path can vary. For example, the physics animation pipeline has dedicated dispatch and rendering services, while the Remotion renderer uses scene data to produce animated compositions.

## Architecture

The repository contains three main application areas.

| Component | Responsibility |
|---|---|
| `backend/` | Python application, LangGraph workflow, research, writing, scene planning, narration, rendering services, and API |
| `frontend/` | Next.js web interface for requesting and tracking video-generation jobs |
| `remotion/` | React and TypeScript video compositions and the Remotion rendering workflow |

### Backend workflow

The LangGraph workflow coordinates the steps required to turn a topic into a video. Its graph state carries information between nodes, while individual nodes perform tasks such as research, script generation, evaluation, revision, and scene planning.

Relevant files include:

- `backend/app/graph/workflow.py` — workflow orchestration.
- `backend/app/graph/state.py` — shared workflow state.
- `backend/app/graph/nodes.py` — workflow node implementations.
- `backend/app/graph/scene_planner.py` — scene planning and visual selection.
- `backend/run_graph.py` — command-line entry point.
- `backend/app/services/` — supporting services, including physics animation and video rendering.

### Web API

The FastAPI backend exposes endpoints for health checks and video-generation jobs.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Check whether the API is responding |
| `POST /api/jobs` | Submit a video-generation job |
| `GET /api/jobs/{job_id}` | Retrieve a job's status |
| `GET /api/jobs/{job_id}/video` | Retrieve the generated video |

Jobs move through states such as `queued`, `running`, `completed`, and `failed`. Generated web-job artifacts are stored under `backend/generated/web_jobs/`.

## Technology Stack

- **Python** — backend and generation pipeline.
- **LangGraph** — workflow orchestration and state management.
- **FastAPI** — HTTP API.
- **Next.js and React** — web interface.
- **TypeScript and Remotion** — animated video compositions.
- **FFmpeg** — media processing and alternative rendering.
- **Manim** — specialized mathematical and physics animations.
- **Google Gemini** — optional AI-powered generation and planning.
- **Edge TTS** — narration generation.
- **SQLite** — local workflow checkpointing where configured.

## Getting Started

### Prerequisites

Install the following tools before setting up the project:

- Git
- Python and `pip`
- Node.js and npm
- FFmpeg, including `ffprobe`
- The dependencies required by the selected renderer

A compatible Gemini API key is optional if you want to use Gemini-powered features. Some physics animation paths may also require Manim and its system dependencies.

### 1. Clone the repository

```bash
git clone https://github.com/Elizabeth-NN/video-explainer-agent.git
cd video-explainer-agent
```

### 2. Set up the Python backend

```bash
cd backend

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Return to the repository root when you need to work on the frontend or Remotion application:

```bash
cd ..
```

If your virtual environment is located inside `backend/`, activate it again when opening a new terminal:

```bash
cd ~/Development/code/personal/video-explainer-agent/backend
source .venv/bin/activate
```

### 3. Configure environment variables

Create a local environment file using the repository's environment template, if provided:

```bash
cp .env.example .env
```

Edit the file and add any credentials required by the features you intend to use. Keep real credentials private and never commit them to Git.

If the environment template is stored in a subdirectory, use that template instead. Check the backend configuration to confirm which directory loads the environment file.

### 4. Install frontend dependencies

```bash
cd frontend
npm install
```

### 5. Install Remotion dependencies

```bash
cd ../remotion
npm install
```

## Environment Configuration

The exact environment variables depend on the enabled features and the configuration implemented in the repository.

| Setting | Purpose |
|---|---|
| `GEMINI_API_KEY` | Enables authenticated Gemini requests |
| `GEMINI_MODEL` | Selects the Gemini model; the configured model has included `gemini-3.1-flash-lite` |
| `REMOTION_MANIFEST_PATH` | Allows Remotion preparation to use a specific narration manifest instead of the default manifest path |

The CLI can run without the optional Gemini writer when the deterministic fallback is available. Requests to external AI services may fail because of network issues, rate limits, or service availability.

Do not assume that every variable listed here is required for every workflow. Check the application's configuration and `.env.example` before adding new variables.

## Generate a Video from the CLI

Run CLI commands from the `backend/` directory with the Python environment activated.

### Generate an explanation

```bash
python run_graph.py "How does binary search work?"
```

This runs the workflow without explicitly enabling the optional Gemini writer or video rendering.

### Use Gemini

```bash
python run_graph.py "How does solar energy work?" --gemini
```

### Select a subject category

```bash
python run_graph.py "How does binary search work?" --category cs
```

For a physics topic:

```bash
python run_graph.py "How does solar energy work?" --category physics
```

The supported category values are `cs` and `physics`.

### Generate narration

```bash
python run_graph.py "How does a CPU cache work?" --audio
```

### Generate a video

```bash
python run_graph.py "How does binary search work?" --video
```

### Choose a renderer

```bash
python run_graph.py "How does binary search work?" --video --renderer remotion
```

The CLI also supports the FFmpeg renderer:

```bash
python run_graph.py "How does binary search work?" --video --renderer ffmpeg
```

### Choose the narration voice

```bash
python run_graph.py "How does binary search work?" \
  --audio \
  --voice en-US-JennyNeural
```

### Choose an output directory

```bash
python run_graph.py "How does binary search work?" \
  --video \
  --output-dir generated/my-binary-search-video
```

### Combine options

```bash
python run_graph.py "How does binary search work?" \
  --category cs \
  --gemini \
  --audio \
  --video \
  --renderer remotion \
  --voice en-US-JennyNeural \
  --output-dir generated/binary-search
```

Additional options include `--semantic-graphs` and `--visual-planner`. Run the CLI help command to see the options available in your current checkout:

```bash
python run_graph.py --help
```

Output files depend on the selected workflow and rendering options. Inspect the chosen output directory and its manifest to identify the generated script, scene data, narration, and final video.

## Web Interface

The web interface lets a user submit a topic without invoking the CLI manually. The frontend communicates with the FastAPI backend, which queues a job and runs the generation workflow.

### Start the backend API

From the repository root:

```bash
cd backend
source .venv/bin/activate
uvicorn app.api:app --reload --host 127.0.0.1 --port 8000
```

Check the health endpoint:

```bash
curl http://127.0.0.1:8000/api/health
```

A healthy API should return a JSON response indicating that the service is available.

### Start the frontend

Open a second terminal:

```bash
cd frontend
npm run dev
```

Open the local URL printed by Next.js, normally `http://localhost:3000`.

The backend is configured for local frontend development on port `3000`. If you change either port or the frontend's API configuration, update the relevant settings accordingly.

### Job output

Web-generated files are written to:

```text
backend/generated/web_jobs/<job_id>/
```

The final video is expected at:

```text
backend/generated/web_jobs/<job_id>/explainer.mp4
```

The API exposes the job's status and video endpoint. A completed job should have a final video available; failed jobs should be investigated through the backend logs and job output.

## Video Rendering

The project has multiple rendering paths rather than a single renderer.

### Remotion

The Remotion application uses React and TypeScript to produce animated scenes. Its composition logic is in `remotion/src/Explainer.tsx`, with visual components under `remotion/src/visuals/`.

To prepare the renderer using the default narration manifest:

```bash
cd remotion
node scripts/prepare.mjs
```

To start the Remotion Studio:

```bash
npm run studio
```

To use a specific narration manifest during preparation:

```bash
REMOTION_MANIFEST_PATH="../backend/generated/<your-output>/manifest.json" \
  node scripts/prepare.mjs
```

Replace the example path with the manifest generated by your run. Follow the repository's Remotion scripts for the exact preview or rendering command available in your checkout.

**Audio alignment matters:** each scene's `audioFile` must reference the correct narration file for that video. When preparing multiple videos, avoid reusing audio files from another run. Confirm the scene manifest, audio paths, and rendered result before considering a video complete.

### FFmpeg

The FFmpeg renderer provides an alternative video-generation path. It depends on the installed FFmpeg tools and the rendering implementation in the backend.

Use `--renderer ffmpeg` when selecting this path through the CLI.

### Rendering recommendations

- Preview the scene sequence before a full render when possible.
- Check that narration matches the visuals scene by scene.
- Confirm the final video's duration and audio.
- Keep generated videos and intermediate artifacts in dedicated output directories.
- Use low rendering concurrency on memory-constrained machines.

## Physics Animation Pipeline

Physics has dedicated animation and rendering services in addition to the general scene-planning workflow.

Relevant code includes:

- `backend/app/services/physics_animation_dispatcher.py`
- `backend/app/services/physics_video_renderer.py`
- `backend/app/science/physics/`

The dispatcher selects a suitable physics animation path based on the available topic and scene information. The rendering service coordinates the production of the corresponding clip.

The physics pipeline and the general Remotion scene planner are related parts of the application, but they should not be assumed to be interchangeable. Which path is used depends on the workflow and rendering integration for the topic.

When adding a physics concept:

1. Identify the appropriate existing animation or scene type.
2. Check how the dispatcher matches topics to scenes.
3. Ensure the scene represents the relevant physical process accurately.
4. Verify how the generated clip is integrated with the rest of the video.
5. Test the output and confirm that the narration and animation agree.

## Testing

### Backend tests

Activate the Python virtual environment and run:

```bash
cd backend
source .venv/bin/activate
python -m pytest -q tests/
```

Run an individual test module when investigating a specific feature:

```bash
python -m pytest -q tests/test_scene_planner.py
```

### Frontend checks

```bash
cd frontend
npx tsc --noEmit
npm run lint
npm run build
```

### Remotion checks

```bash
cd remotion
npx tsc --noEmit
```

The repository may also contain tests for specific Remotion compositions and visual logic. Run the relevant tests when changing scene timing, visual components, or audio behavior.

### Before submitting a change

- Run the tests relevant to the code you changed.
- Check formatting and whitespace:

  ```bash
  git diff --check
  ```

- Preview or render an example when changing visuals or narration.
- Check the Git diff before committing.
- Do not commit API keys, local environment files, or generated media unintentionally.

## Project Structure

```text
video-explainer-agent/
├── backend/
│   ├── app/
│   │   ├── graph/
│   │   │   ├── workflow.py
│   │   │   ├── state.py
│   │   │   ├── nodes.py
│   │   │   └── scene_planner.py
│   │   ├── services/
│   │   └── science/
│   │       └── physics/
│   ├── tests/
│   ├── run_graph.py
│   └── requirements.txt
├── frontend/
│   └── ...
├── remotion/
│   ├── src/
│   │   ├── Explainer.tsx
│   │   └── visuals/
│   ├── scripts/
│   └── package.json
├── docs/
├── generated/
└── README.md
```

This is a simplified overview of the main application areas, not an exhaustive listing of every file.

## Troubleshooting

### Gemini requests fail

Check that the API key is configured correctly, the selected model is available, and the network request succeeds. Rate limits and temporary service errors can occur. If supported by the selected workflow, run without `--gemini` to use the deterministic path.

### FFmpeg or `ffprobe` cannot be found

Install FFmpeg using the package manager for your operating system, then confirm both commands are available:

```bash
ffmpeg -version
ffprobe -version
```

### Narration does not match the visuals

Inspect the manifest and verify that each scene references its own correct audio file. If audio files from another video have been copied into the same directory, regenerate or isolate the assets before rendering again.

### Remotion cannot find audio files

Check that the audio assets were prepared in the expected public directory and that each `audioFile` path matches the file's location relative to the Remotion public assets.

### Video generation is slow or runs out of memory

Start with a short topic, avoid unnecessary concurrent renders, and use a low concurrency setting. Large animation renders can be resource-intensive.

### The dashboard cannot reach the API

Confirm that the backend is running on the configured host and port, check `GET /api/health`, and verify the frontend API configuration and backend CORS settings.

## Roadmap

Areas for continued development include:

- Improving alignment between narration and animated scene timing.
- Expanding reusable visual patterns for computer science and physics.
- Improving the reliability of topic-to-animation selection.
- Strengthening audio and render artifact isolation between jobs.
- Expanding automated tests for the end-to-end generation pipeline.
- Improving job progress, error reporting, and the user experience in the web interface.

These are development goals, not a claim that every item is already implemented.

## Contributing

Contributions and improvements are welcome.

1. Create a branch for your change.
2. Keep changes focused and explain the reason for them.
3. Add or update tests where appropriate.
4. Run the relevant backend, frontend, and rendering checks.
5. Preview generated videos when modifying narration, scene planning, or animation behavior.
6. Review your diff before opening a pull request.

## License

Add the repository's chosen license here. Until a license is included, do not assume the project is available for unrestricted reuse or redistribution.
