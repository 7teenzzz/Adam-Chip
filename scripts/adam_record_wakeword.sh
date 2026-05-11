#!/usr/bin/env bash
# Record wake word samples for one speaker.
#
# Usage:
#   ./scripts/adam_record_wakeword.sh <speaker_id>
#
# Examples:
#   ./scripts/adam_record_wakeword.sh speaker_1_male
#   ./scripts/adam_record_wakeword.sh speaker_2_male
#   ./scripts/adam_record_wakeword.sh speaker_3_female
#   ./scripts/adam_record_wakeword.sh speaker_4_female
#
# Saves to:
#   data/wake_word/speakers/<speaker_id>/positive/  — "адам" recordings
#   data/wake_word/speakers/<speaker_id>/negative/  — other phrases
#
# After all 4 speakers recorded, run:  ./scripts/adam_train_wakeword.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIC_DEVICE="${ADAM_AUDIO_INPUT_DEVICE:-pulse}"
SAMPLE_RATE=16000
CHANNELS=1
DURATION_SEC=2    # each clip: "адам" takes ~0.5s, padded to 2s
PAUSE_SEC=1       # pause between recordings

# ---- speaker ID argument ----------------------------------------------------
SPEAKER_ID="${1:-}"
if [[ -z "${SPEAKER_ID}" ]]; then
  echo "Использование: $0 <speaker_id>"
  echo "Пример:       $0 speaker_1_male"
  echo ""
  echo "Стандартный порядок для 4 дикторов:"
  echo "  $0 speaker_1_male"
  echo "  $0 speaker_2_male"
  echo "  $0 speaker_3_female"
  echo "  $0 speaker_4_female"
  exit 1
fi

SPEAKER_DIR="${ROOT_DIR}/data/wake_word/speakers/${SPEAKER_ID}"
POS_DIR="${SPEAKER_DIR}/positive"
NEG_DIR="${SPEAKER_DIR}/negative"

mkdir -p "${POS_DIR}" "${NEG_DIR}"

# ---- helpers ----------------------------------------------------------------
pause() { read -rp "  [Enter для продолжения...]" _ || true; }

record_clip() {
  local outfile="$1" phrase="$2" idx="$3" total="$4"
  echo "  🎙️  Скажи: «${phrase}»  (${idx}/${total})"
  printf "     Запись через: "
  for c in 3 2 1; do printf "%s... " "${c}"; sleep 1; done
  printf "\n     ● ЗАПИСЬ\n"
  arecord -D "${MIC_DEVICE}" -r "${SAMPLE_RATE}" -c "${CHANNELS}" \
          -f S16_LE -d "${DURATION_SEC}" "${outfile}" 2>/dev/null
  echo "     ■ Сохранено → $(basename "${outfile}")"
  sleep "${PAUSE_SEC}"
}

# ---- intro ------------------------------------------------------------------
EXISTING_POS=$(find "${POS_DIR}" -name "*.wav" 2>/dev/null | wc -l)
EXISTING_NEG=$(find "${NEG_DIR}" -name "*.wav" 2>/dev/null | wc -l)

cat <<MSG

▶ Запись для диктора: ${SPEAKER_ID}
  Позитивных уже: ${EXISTING_POS}  Негативных уже: ${EXISTING_NEG}
  ────────────────────────────────────────────────────────
  Держи микрофон на обычном расстоянии (~30-50 см от лица).
  Говори естественно, как при разговоре с Адамом.
MSG

# Check if orchestrator is running and mic might be busy
if pgrep -f 'System/Orchestrator\.py' >/dev/null 2>&1; then
  echo "  ⚠️  Оркестратор Адама запущен — микрофон может быть занят!"
  read -rp "  Остановить оркестратор? [Y/n] " ans
  if [[ ! "${ans}" =~ ^[Nn]$ ]]; then
    pkill -f 'System/Orchestrator\.py' 2>/dev/null && echo "  ✓ Остановлен" || true
    sleep 1
  fi
fi

echo
pause

# ---- 1. Positive samples: «адам» -------------------------------------------
echo
echo "▶ Часть 1 из 2: скажи «адам» — 20 раз"
echo "  Варьируй интонацию: тихо, громко, быстро, медленно, вопросительно, утвердительно."
echo

START_IDX=$((EXISTING_POS + 1))
for i in $(seq "${START_IDX}" $((START_IDX + 19))); do
  outfile="${POS_DIR}/adam_$(printf '%03d' "${i}").wav"
  record_clip "${outfile}" "адам" "${i}" "$((START_IDX + 19))"
done

POS_TOTAL=$(find "${POS_DIR}" -name "*.wav" | wc -l)
echo
echo "  ✓ Позитивных образцов: ${POS_TOTAL}"

# ---- 2. Negative samples: other phrases ------------------------------------
echo
echo "▶ Часть 2 из 2: скажи другие фразы — 20 раз (НЕ «адам»)"
echo "  Это учит систему отличать «адам» от любой другой речи."
echo

NEG_PHRASES=(
  "привет как дела"
  "всё хорошо спасибо"
  "раз два три"
  "включи пожалуйста свет"
  "который сейчас час"
  "стоп остановись"
  "покажи мне это"
  "да конечно понятно"
  "нет не нужно"
  "расскажи что ты видишь"
  "я здесь слышишь меня"
  "послушай что я скажу"
  "что сейчас происходит"
  "как тебя зовут"
  "ты понимаешь меня"
  "сделай это пожалуйста"
  "хорошо договорились"
  "подожди одну секунду"
  "спасибо за ответ"
  "окей продолжай"
)

NEG_START=$((EXISTING_NEG + 1))
for i in "${!NEG_PHRASES[@]}"; do
  idx=$((NEG_START + i))
  outfile="${NEG_DIR}/neg_$(printf '%03d' "${idx}").wav"
  record_clip "${outfile}" "${NEG_PHRASES[$i]}" "$((i + 1))" "20"
done

NEG_TOTAL=$(find "${NEG_DIR}" -name "*.wav" | wc -l)
echo
echo "  ✓ Негативных образцов: ${NEG_TOTAL}"

# ---- summary ----------------------------------------------------------------
SPEAKERS_DONE=$(find "${ROOT_DIR}/data/wake_word/speakers" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
cat <<SUMMARY

▶ Диктор ${SPEAKER_ID} записан.
  Позитивных: ${POS_TOTAL}  Негативных: ${NEG_TOTAL}
  Всего дикторов записано: ${SPEAKERS_DONE}

SUMMARY

if [[ "${SPEAKERS_DONE}" -ge 4 ]]; then
  echo "  ✅ Все 4 диктора записаны! Можно переобучать:"
  echo "     sudo systemctl start adam-tts-silero.service && sleep 8"
  echo "     ./scripts/adam_train_wakeword.sh"
else
  REMAINING=$((4 - SPEAKERS_DONE))
  echo "  ⏳ Осталось записать ещё ${REMAINING} диктора(ов)."
  echo "  Следующий:  ./scripts/adam_record_wakeword.sh <speaker_id>"
fi
