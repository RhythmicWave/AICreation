# <p align="center">AI Creation - Smart Creative Content Generation System</p>

<div align="center">

[中文](README.md) | [English](README_EN.md)

[Features](#features) | [Installation](#installation) | [Running](#running) | [Configuration](#configuration) | [Usage Guide](#usage-guide) | [Project Structure](#project-structure)

</div>

## Features

This project is an intelligent creative content generation system, which can help users:
- Quickly generate creative text content
- Generate images using AI technology
- Automatically synthesize videos
- Maintain image generation consistency through entity management

System Architecture:
- Frontend: VUE3 + TypeScript + Element Plus
- Backend: Python FastAPI framework
- AI Model: OpenAI-compatible API interface, using LangChain for LLM integration
- Image Generation: Integrated with ComfyUI
- Audio Generation: Integrated with EdgeTTS
- Content Management: File system-based structured storage

### Demo Video



https://github.com/user-attachments/assets/5dbdd094-0878-4041-8036-3068e022a6f9


## Installation

### Requirements
- Python >= 3.10
- Node.js
- ComfyUI

### Setup Steps

1. Install Backend Dependencies
```bash
cd server
pip install -r requirements.txt
```

2. Install Frontend Dependencies
```bash
cd client
npm install
```

3. ComfyUI Model Configuration
- Reference tutorial: https://zhuanlan.zhihu.com/p/1898355945110759141

## Running

1. Start Backend Server
```bash
cd server
python app.py
```

2. Start Frontend Server
```bash
cd client
npm run dev
```

3. Launch ComfyUI
- Default workflow: nunchaku-flux (requires 10GB+ VRAM)
- Workflow path: `server/workflow` (extensible)

> **Note**: When using the default workflow, ensure all required models are downloaded and properly placed. For non-50 series GPUs, replace the svdq-fp4-flux.1-dev model with the int4 version.

![ComfyUI Workflow Configuration](docs/image7.png)

## Configuration

1. Access System Configuration Page
![Configuration Page](docs/image.png)

2. Configure LLM Service
![LLM Configuration](docs/image2.png)

Key Configuration Items:
- ComfyUI API URL
- LLM API URL
- API Key
- Model Name

> **No Key? Get API Key**:
> Register through [this link](https://cloud.siliconflow.cn/i/Je8e1K0b) to receive 20 million free tokens
> After registration, go to: API Keys → Create New API Key

## Usage Guide

### 1. Create Project

### 2. Text Creation
- Creation Mode: Input requirements directly for AI generation
- Continuation Mode: Input existing text for AI to continue

### 3. Character Extraction
![Character Extraction](docs/image3.png)
- Click "Extract Characters" after saving text
- AI analyzes text and extracts character information
- View results in character library

### 4. Chapter Segmentation
![Chapter Segmentation](docs/image4.png)
- Click "Split Current Chapter"
- System automatically extracts scenes and creates storyboards

### 5. Storyboard Processing
![Storyboard Processing](docs/image5.png)

a) Prompt Conversion:
- Select all elements
- Click "Convert Selected Prompts"
- Save changes

b) Image Generation:
- Configure resolution and style
- Click "Generate Selected Images"
- Support individual regeneration

c) Audio Generation:
- Select desired segments
- Click generate audio

### 6. Video Generation
![Video Generation](docs/image6.png)
- Switch to video generation interface
- When setting the horizontal pan range or vertical pan range, the width or height of the video resolution can be automatically adjusted. However, automatic adjustment is not possible when both the horizontal and vertical pan ranges are set simultaneously.
- Click "Generate Video" (takes about 1 minute)

#### Video Hardware Encoding Configuration (Optional)

To enable NVIDIA GPU acceleration (NVENC):

1. Download and extract FFmpeg Builds
2. Configure environment variables:
   - Add FFmpeg bin directory to PATH
   - Ensure NVIDIA drivers are installed
3. Verify configuration:
   ```bash
   ffmpeg -encoders | findstr nvenc
   ```
   Configuration is successful if h264_nvenc is displayed

> Note: CPU encoding will be used automatically if not configured

## Project Structure

```
AICreation/                # Project root
├── client/               # Frontend code
│   ├── src/             # Source code directory
│   ├── public/          # Static resources
│   └── package.json     # Project configuration
├── server/              # Server-side code
│   ├── config/          # Configuration files
│   ├── controllers/     # API interface layer
│   ├── services/        # Business logic layer
│   ├── utils/           # Utility classes
│   ├── prompts/         # Prompt templates
│   └── workflow/        # Workflow configuration
├── projects/            # Project data storage
└── README.md           # Project documentation
```

Detailed Directory Structure:

```
AICreation/                # Project root
├── client/               # Frontend code
│   ├── src/             # Source code directory
│   │   ├── api/         # API interface directory
│   │   │   ├── project_api.ts # Project-related API
│   │   │   ├── chapter_api.ts # Chapter-related API
│   │   │   ├── entity_api.ts # Entity-related API
│   │   │   ├── media_api.ts # Media generation API
│   │   │   └── request.ts # Request wrapper (Axios & Fetch API)
│   │   ├── components/   # Components directory
│   │   │   ├── Header.vue # Navigation header component
│   │   ├── locales/     # Internationalization directory
│   │   │   ├── en-US.ts # English language pack
│   │   │   ├── zh-CN.ts # Chinese language pack
│   │   │   └── index.ts # i18n configuration
│   │   ├── router/      # Router configuration
│   │   │   └── index.ts # Router configuration file
│   │   ├── store/       # State management
│   │   ├── styles/      # Style files
│   │   ├── utils/       # Utility classes
│   │   ├── views/       # Page views
│   │   │   ├── Project/ # Project management
│   │   │   │   └── index.vue
│   │   │   ├── ProjectMain/ # Project details
│   │   │   │   ├── index.vue # Main project page
│   │   │   │   ├── CharacterLibrary/ # Character management
│   │   │   │   │   └── index.vue
│   │   │   │   ├── SceneLibrary/ # Scene management
│   │   │   │   │   └── index.vue
│   │   │   │   ├── StoryboardProcess/ # Storyboard workflow
│   │   │   │   │   └── index.vue
│   │   │   │   ├── TextCreation/ # Text creation
│   │   │   │   │   └── index.vue
│   │   │   │   └── VideoOutput/ # Video output
│   │   │   │       └── index.vue
│   │   │   ├── Setting/ # Settings page
│   │   │   │   └── index.vue
│   │   │   └── NotFound/ # 404 page
│   │   │       └── index.vue
│   │   ├── App.vue      # Root component
│   │   ├── main.ts      # Entry file
│   │   └── env.d.ts     # Type declarations
│   ├── public/          # Static resources
│   ├── index.html       # HTML template
│   ├── package.json     # Project configuration
│   ├── tsconfig.json    # TypeScript configuration
│   └── vite.config.ts   # Vite configuration
├── server/               # Server-side code
│   ├── config/          # Configuration files
│   ├── controllers/     # API interface layer
│   ├── services/        # Business logic layer
│   ├── utils/           # Utility classes
│   ├── prompts/         # Prompt templates
│   └── workflow/        # Workflow configuration
├── projects/            # Project data storage
└── README.md           # Project documentation
``` 
