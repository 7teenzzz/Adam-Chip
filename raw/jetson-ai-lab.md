---
source_url: https://www.jetson-ai-lab.com/
captured_at: 2026-05-15
author: NVIDIA
contributor: graphify-add
---

# Jetson AI Lab

## Overview

Jetson AI Lab is NVIDIA's platform for "bringing generative AI to the world with NVIDIA Jetson." The site provides resources for deploying and running AI models locally on edge devices without cloud dependency.

## Platform Purpose

Deploy and run LLMs, VLMs, and diffusion models on NVIDIA Jetson hardware (Orin NX, Orin Nano, AGX Orin, AGX Thor) using optimized Docker containers and inference stacks.

## Tutorial Areas

- **Getting Started**: Device setup and development environment configuration (JetPack, SDK Manager)
- **Fundamentals**: Core concepts for running generative AI on Jetson hardware
- **Vision-Language Models (VLM)**: Multimodal reasoning — VILA, LLaVA, NanoLLM
- **Vision-Language-Action (VLA)**: Robotic control applications — GR00T, Pi0
- **Applications**: End-to-end AI solutions and microservices
- **Model Optimization**: Fine-tuning, quantization (GGUF, AWQ, INT4), edge deployment
- **Workshops & Hackathons**: Hands-on training and competitive events

## Supported Models and Frameworks

- **LLMs**: Llama, Mistral, Phi, Gemma via llama.cpp, ollama, TensorRT-LLM
- **VLMs**: VILA 1.5, LLaVA, InternVL — optimized for Jetson CUDA
- **VLA**: GR00T N1.5, Alpamayo R1 (10.5B)
- **Diffusion**: Stable Diffusion via TensorRT
- **ASR**: Whisper via faster-whisper / WhisperX with CUDA acceleration
- **TTS**: Silero, Piper, Kokoro

## Docker Containers (Jetson Containers project)

Available at github.com/dusty-nv/jetson-containers:
- Pre-built images for JetPack 5.x / 6.x
- Containers: `l4t-pytorch`, `l4t-tensorflow`, `whisper`, `stable-diffusion`, `llm`
- CUDA-enabled PyTorch wheels for aarch64

## Hardware Requirements

- **Jetson Orin NX 16GB**: Runs 7B-13B models at real-time, VLMs at 2-5 fps
- **Jetson AGX Orin 64GB**: Runs 30B+ models, 20-30 fps VLM
- **Jetson Orin Nano**: 3B-7B models, lighter inference tasks
- JetPack 5.1+ or JetPack 6.x recommended
- NVMe storage recommended for model storage (70GB+ for large LLMs)

## Key Technical Details for Adam Chip Integration

- **WhisperX on Jetson**: ctranslate2 must be compiled from source with CUDA flag for aarch64 — pip package is CPU-only
- **PyTorch install order**: Always install Jetson-compatible wheel first, then `pip install --no-deps` for dependent packages
- **llama.cpp**: CUDA backend (cuBLAS) required for GPU inference; cmake build with `-DLLAMA_CUDA=ON`
- **VLM (VILA 1.5-3b)**: Runs via nano_llm Docker container, port 8084
- **MAXN power mode**: `nvpmodel -m 0` + `jetson_clocks` required for exhibition performance

## Community Applications

- Autonomous vehicle retrofitting (Jetson AGX Thor)
- Robotic microfarm systems (Jetson Orin Nano)
- Exhibition AI agents — multimodal interaction with camera + audio
