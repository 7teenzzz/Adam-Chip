---
source_url: https://github.com/snakers4/silero-models
captured_at: 2026-05-15
author: snakers4
contributor: graphify-add
---

# Silero Models: Text-to-Speech Overview

## What Are Silero Models?

Silero Models provides pre-trained text-to-speech (TTS) models designed for simplicity and accessibility. The models are described as "fully end-to-end" with "natural-sounding speech," offering "one-line usage, minimal, portable" implementation. They perform efficiently on both CPU and GPU, and Russian language models include automated stress and homograph handling.

## Installation

Three usage approaches are available:

1. **PyTorch Hub**: `torch.hub.load()`
2. **pip package**: `pip install silero` then `from silero import silero_tts`
3. **Manual caching**: Download models directly for custom modifications

Models download on-demand to a cache folder upon first use.

## Model Versions and Languages

### V5 Models (Latest)

**V5.5_ru (Russian)** - Most recent iteration
- **Speakers**: aidar, baya, kseniya, xenia, eugene
- **Stress automation**: Yes, handles stress and homograph disambiguation automatically
- **Sample rates**: 8000, 24000, 48000 Hz
- **SSML support**: Yes

**V5 CIS Base Models** (MIT License)
- Support 25+ languages including Russian, Ukrainian, Kazakh, Tatar, Georgian, Armenian, Azerbaijani, Uzbek, and others
- **Stress notation requirement**: All languages need marked stress (e.g., `к+ошка`)
- **Nostress variant**: Slavic languages only require stress marking
- **Features**: SSML support, multiple speakers per language

**V5 CIS Extended Models** (CC-NC-BY License)
- Expanded speaker selection for Kazakh, Kalmyk, Tatar, Ukrainian, and Chuvash

### V4 Models

- **v4_ru**: Russian with 6 speakers
- **v4_cyrillic**: Multiple Cyrillic script languages
- **v4_ua**: Ukrainian
- **v4_uz**: Uzbek
- **v4_indic**: Hindi, Telugu, Tamil, Bengali, Gujarati, Kannada, Malayalam, Rajasthani, and Manipuri

### V3 Models

- **v3_en**: 118+ English speakers
- **v3_en_indic**: Indic language speakers with English text
- **v3_de, v3_es, v3_fr**: German, Spanish, French

## Basic Usage Example

```python
import torch

language = 'ru'
model_id = 'v5_ru'
sample_rate = 48000
speaker = 'xenia'
device = torch.device('cpu')

model, example_text = torch.hub.load(repo_or='snakers4/silero-models',
                                     model='silero_tts',
                                     language=language,
                                     speaker=model_id)
model.to(device)

audio = model.apply_tts(text=example_text,
                        speaker=speaker,
                        sample_rate=sample_rate)
```

## Standalone Implementation

Requires only PyTorch 1.12+ and Python Standard Library:

```python
import torch
import os

device = torch.device('cpu')
local_file = 'model.pt'

if not os.path.isfile(local_file):
    torch.hub.download_url_to_file(
        'https://models.silero.ai/models/tts/ru/v5_ru.pt',
        local_file)

model = torch.package.PackageImporter(local_file).load_pickle(
    "tts_models", "model")
model.to(device)

audio_paths = model.save_wav(text="Example text",
                             speaker='baya',
                             sample_rate=48000)
```

## Key Features

- **SSML Support**: V4 and V5 models support Speech Synthesis Markup Language for advanced control
- **Stress Automation**: Russian V5 models handle stress and homograph disambiguation automatically
- **Multi-language Support**: Coverage spans Slavic, Caucasian, Turkic, and Indic language families

## Dependencies

- PyTorch 1.10+ (v3 models) or 2.0+ (v4/v5 models)
- torchaudio (latest version compatible with PyTorch)
- Install for Jetson: use Jetson-compatible wheel first, then `pip install --no-deps "silero>=0.5.0"`

## Licensing

- **V5 CIS Base models**: MIT license
- **Main repository models**: CC-NC-BY license

## Jetson-specific Notes

- Install order is critical: Jetson-compatible PyTorch wheel FIRST, then `pip install --no-deps "silero>=0.5.0"`
- Dependency resolver breaks Jetson PyTorch if silero is installed normally
- v5_5_ru model uses eugene speaker by default in Adam Chip
- Output sample rate: 24000 Hz — do not change without rebuilding TTS service
