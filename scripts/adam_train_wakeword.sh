#!/usr/bin/env bash
# Train a custom wake word verifier for "адам" using Silero TTS synthetic data.
#
# Usage:
#   ./scripts/adam_train_wakeword.sh
#
# Requirements:
#   - Silero TTS running on port 8082 (adam-tts-silero.service)
#   - openWakeWord installed in .venv
#
# Output:
#   data/wake_word/adam_verifier.pkl   — sklearn LogisticRegression verifier

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
WAKEWORD_DIR="${ROOT_DIR}/data/wake_word"
TTS_URL="http://127.0.0.1:8082"
SPEAKERS=(aidar eugene kseniya xenia baya)
POSITIVE_PHRASES=("адам" "Адам" "адам!")
NEGATIVE_PHRASES=(
  "привет" "стоп" "раз" "два" "три" "один" "пять"
  "да" "нет" "хорошо" "понятно" "отлично" "спасибо"
  "что" "как" "когда" "где" "зачем" "почему"
  "включи" "выключи" "покажи" "расскажи" "ответь"
  "музыка" "погода" "время" "дата" "новости"
  "сегодня хорошая погода за окном"
  "расскажи мне что-нибудь интересное"
  "который сейчас час скажи пожалуйста"
  "включи музыку потихоньку"
  "что происходит в мире сегодня"
  "я хочу узнать больше об этом"
  "покажи мне последние новости"
  "какая температура на улице сейчас"
  "это очень интересная история получается"
  "можешь объяснить мне как это работает"
  "позвони мне когда будешь свободен"
  "напомни завтра в десять утра"
  "сколько стоит поездка до центра"
  "открой браузер и найди информацию"
)

mkdir -p "${WAKEWORD_DIR}/positive" "${WAKEWORD_DIR}/negative"

# ---- 1. Check TTS availability -----------------------------------------------
echo "▶ Проверка Silero TTS на ${TTS_URL}..."
if ! curl --noproxy '*' -fsS "${TTS_URL}/health" >/dev/null 2>&1; then
  echo "✗ Silero TTS недоступен. Запусти: sudo systemctl start adam-tts-silero.service" >&2
  exit 1
fi
echo "  ✓ TTS готов"

# ---- 2. Generate positive samples --------------------------------------------
echo
echo "▶ Генерация позитивных примеров (адам)..."
POS_COUNT=0
for speaker in "${SPEAKERS[@]}"; do
  for phrase in "${POSITIVE_PHRASES[@]}"; do
    for i in $(seq 1 6); do
      outfile="${WAKEWORD_DIR}/positive/adam_${speaker}_${i}_$(echo "${phrase}" | md5sum | cut -c1-4).wav"
      if [[ -f "${outfile}" ]]; then continue; fi
      curl --noproxy '*' -fsS "${TTS_URL}/wav" \
        -H "Content-Type: application/json" \
        -d "{\"text\":\"${phrase}\",\"speaker\":\"${speaker}\"}" \
        -o "${outfile}" 2>/dev/null && POS_COUNT=$((POS_COUNT+1)) || true
    done
  done
done
TOTAL_POS=$(find "${WAKEWORD_DIR}/positive" -name "*.wav" | wc -l)
echo "  ✓ Позитивных примеров: ${TOTAL_POS}"

# ---- 3. Generate negative samples --------------------------------------------
echo
echo "▶ Генерация негативных примеров..."
for speaker in aidar eugene kseniya; do
  for phrase in "${NEGATIVE_PHRASES[@]}"; do
    outfile="${WAKEWORD_DIR}/negative/neg_${speaker}_$(echo "${phrase}" | md5sum | cut -c1-6).wav"
    if [[ -f "${outfile}" ]]; then continue; fi
    curl --noproxy '*' -fsS "${TTS_URL}/wav" \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"${phrase}\",\"speaker\":\"${speaker}\"}" \
      -o "${outfile}" 2>/dev/null || true
  done
done
TOTAL_NEG=$(find "${WAKEWORD_DIR}/negative" -name "*.wav" | wc -l)
echo "  ✓ Негативных примеров: ${TOTAL_NEG}"

# ---- 4. Train verifier -------------------------------------------------------
echo
echo "▶ Обучение верификатора..."
WAKEWORD_DIR="${WAKEWORD_DIR}" "${VENV_PYTHON}" - <<'PYEOF'
import os, sys, glob, pickle
import numpy as np
import scipy.io.wavfile
import collections
import openwakeword

WAKEWORD_DIR = os.environ["WAKEWORD_DIR"]
POS_DIR = os.path.join(WAKEWORD_DIR, "positive")
NEG_DIR = os.path.join(WAKEWORD_DIR, "negative")
SPEAKERS_DIR = os.path.join(WAKEWORD_DIR, "speakers")
OUT_PATH = os.path.join(WAKEWORD_DIR, "adam_verifier.pkl")

# Discover real speaker directories from adam_record_wakeword.sh
speaker_dirs = []
if os.path.isdir(SPEAKERS_DIR):
    speaker_dirs = sorted([
        d for d in os.listdir(SPEAKERS_DIR)
        if os.path.isdir(os.path.join(SPEAKERS_DIR, d))
    ])

tts_pos_count = len(glob.glob(POS_DIR + "/*.wav"))
tts_neg_count = len(glob.glob(NEG_DIR + "/*.wav"))
real_pos_count = sum(
    len(glob.glob(os.path.join(SPEAKERS_DIR, spk, "positive", "*.wav")))
    for spk in speaker_dirs
)
real_neg_count = sum(
    len(glob.glob(os.path.join(SPEAKERS_DIR, spk, "negative", "*.wav")))
    for spk in speaker_dirs
)
print(f"  Positive clips — TTS: {tts_pos_count}, real speakers: {real_pos_count} ({len(speaker_dirs)} дикторов)")
print(f"  Negative clips — TTS: {tts_neg_count}, real speakers: {real_neg_count}")

# Load any base model — we only need the preprocessor (audio feature extractor)
oww = openwakeword.Model(inference_framework="onnx")
model_name = list(oww.models.keys())[0]
n_frames = oww.model_inputs[model_name]

def resample_to_16k(dat, src_sr):
    """Resample int16 audio to 16000 Hz."""
    if src_sr == 16000:
        return dat
    import soxr
    dat_f = dat.astype(np.float32) / 32768.0
    dat_f = soxr.resample(dat_f, src_sr, 16000)
    return (dat_f * 32767).astype(np.int16)


def extract_features(wav_path, threshold=0.0, N=3):
    """Extract audio embeddings from a WAV file using the openWakeWord preprocessor."""
    all_features = []
    for _ in range(N):
        sr, dat = scipy.io.wavfile.read(wav_path)
        if dat.dtype != np.int16:
            dat = (dat * 32767).astype(np.int16)
        if dat.ndim > 1:
            dat = dat[:, 0]
        dat = resample_to_16k(dat, sr)
        if N != 1:
            offset = np.random.randint(0, min(1280, max(1, len(dat) // 4)))
            dat = dat[offset:]
        step = 1280
        for i in range(0, len(dat) - step, step):
            chunk = dat[i:i + step]
            pred = oww.predict(chunk)
            if pred[model_name] >= threshold:
                feats = oww.preprocessor.get_features(n_frames)
                if feats.shape[0] > 0:
                    all_features.append(feats)
    return all_features

# Extract features from TTS synthetic samples (N=3)
print("  Extracting positive features (TTS)...")
pos_features = []
for path in sorted(glob.glob(POS_DIR + "/*.wav")):
    pos_features.extend(extract_features(path, threshold=0.0, N=3))

# Extract features from real speaker recordings (N=5 — more augmentation, fewer clips)
for spk in speaker_dirs:
    spk_pos_dir = os.path.join(SPEAKERS_DIR, spk, "positive")
    clips = sorted(glob.glob(spk_pos_dir + "/*.wav")) if os.path.isdir(spk_pos_dir) else []
    if clips:
        print(f"  Extracting positive features ({spk}, {len(clips)} clips)...")
        for path in clips:
            pos_features.extend(extract_features(path, threshold=0.0, N=5))

if not pos_features:
    print("ERROR: no positive features extracted!", file=sys.stderr)
    sys.exit(1)

# Extract negative features (TTS, N=1)
print("  Extracting negative features (TTS)...")
neg_features = []
for path in sorted(glob.glob(NEG_DIR + "/*.wav")):
    neg_features.extend(extract_features(path, threshold=0.0, N=1))

# Extract negative features from real speakers (N=3)
for spk in speaker_dirs:
    spk_neg_dir = os.path.join(SPEAKERS_DIR, spk, "negative")
    clips = sorted(glob.glob(spk_neg_dir + "/*.wav")) if os.path.isdir(spk_neg_dir) else []
    if clips:
        print(f"  Extracting negative features ({spk}, {len(clips)} clips)...")
        for path in clips:
            neg_features.extend(extract_features(path, threshold=0.0, N=3))

print(f"  Positive vectors: {len(pos_features)}, Negative vectors: {len(neg_features)}")

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# Pre-flatten so no custom function ends up in the pickle
X = np.array([f.flatten() for f in pos_features + neg_features])
labels = np.array([1] * len(pos_features) + [0] * len(neg_features))

clf = LogisticRegression(random_state=0, max_iter=2000, C=0.001, class_weight="balanced")
pipeline = make_pipeline(StandardScaler(), clf)
pipeline.fit(X, labels)

pickle.dump(pipeline, open(OUT_PATH, "wb"))
print(f"  ✓ Saved verifier: {OUT_PATH}")
print(f"  Training accuracy: {pipeline.score(X, labels):.3f}")
PYEOF

echo
echo "▶ Готово. Верификатор: ${WAKEWORD_DIR}/adam_verifier.pkl"
echo ""
echo "  Следующие шаги:"
echo "  1. Открой System/Config.json и измени: \"engine\": \"none\" → \"openwakeword\""
echo "  2. Перезапусти: ./scripts/adam_start.sh"
echo "  3. Проверь: скажи «адам» — должно появиться событие wake_word_detected"
