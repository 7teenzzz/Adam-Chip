#!/usr/bin/env python3
"""Temporary gap-based session reconstructor for pre-session_id records."""
import json, statistics
from datetime import datetime, timezone, timedelta

GAP_MINUTES = 20

with open('/home/i17jet/Agents/Adam-Chip/data/adam/inference_metrics.jsonl') as f:
    turns = [json.loads(l) for l in f if l.strip()]

def parse_ts(s):
    if not s: return None
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except:
        return None

turns.sort(key=lambda t: t.get('ts', ''))

sessions = []
cur = []
for t in turns:
    ts = parse_ts(t.get('ts', ''))
    if not cur:
        cur.append((t, ts))
    else:
        prev_ts = cur[-1][1]
        if prev_ts and ts and (ts - prev_ts) > timedelta(minutes=GAP_MINUTES):
            sessions.append(cur)
            cur = []
        cur.append((t, ts))
if cur:
    sessions.append(cur)

print("Всего turn-ов: %d" % len(turns))
print("Реконструированных сессий (gap>%dмин): %d" % (GAP_MINUTES, len(sessions)))
print()

def pct(vals, p):
    s = sorted(vals)
    i = max(0, min(len(s)-1, int(round(p*(len(s)-1)))))
    return round(s[i])

all_asr = [t[0]['asr_ms'] for s in sessions for t in s if t[0].get('asr_ms') is not None]
all_llm = [t[0]['llm_ms'] for s in sessions for t in s if t[0].get('llm_ms') is not None]
all_tts = [t[0]['tts_ms'] for s in sessions for t in s if t[0].get('tts_ms') is not None]
all_tot = [t[0]['total_ms'] for s in sessions for t in s if t[0].get('total_ms') is not None]

print("=== Задержки (мс) ===")
print("%-8s %5s %6s %6s %6s %7s" % ("Стадия", "N", "min", "avg", "p95", "max"))
print("-" * 42)
for label, vals in [("ASR", all_asr), ("LLM", all_llm), ("TTS", all_tts), ("Total", all_tot)]:
    if vals:
        print("%-8s %5d %6d %6d %6d %7d" % (
            label, len(vals), round(min(vals)),
            round(statistics.mean(vals)), pct(vals, 0.95), round(max(vals))
        ))
print()

def bigrams(text):
    w = (text or '').lower().split()
    return set(zip(w, w[1:]))

def jaccard(a, b):
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)

def session_ri(replies):
    bgs = [bigrams(r) for r in replies if (r or '').strip()]
    if len(bgs) < 2: return 0.0
    pairs = [jaccard(bgs[i], bgs[j]) for i in range(len(bgs)) for j in range(i+1, len(bgs))]
    return round(statistics.mean(pairs), 4) if pairs else 0.0

print("=== Сессии ===")
print("%-4s %-12s %6s %8s %13s %13s" % ("#", "дата", "turns", "dur_мин", "avg_total_мс", "RI_Jaccard"))
print("-" * 62)

for i, sess in enumerate(sessions, 1):
    tss = [t[1] for t in sess if t[1]]
    dur_min = round((max(tss) - min(tss)).total_seconds() / 60, 1) if len(tss) >= 2 else 0
    date = min(tss).strftime('%Y-%m-%d') if tss else '?'
    tot_vals = [t[0]['total_ms'] for t in sess if t[0].get('total_ms') is not None]
    avg_tot = round(statistics.mean(tot_vals)) if tot_vals else 0
    replies = [t[0].get('reply', '') for t in sess]
    ri = session_ri(replies)
    print("%-4d %-12s %6d %8.1f %13d %13.4f" % (i, date, len(sess), dur_min, avg_tot, ri))

durations = []
for sess in sessions:
    tss = [t[1] for t in sess if t[1]]
    if len(tss) >= 2:
        durations.append((max(tss) - min(tss)).total_seconds())
reply_counts = [len(s) for s in sessions]

print()
print("=== Сводка по сессиям ===")
if durations:
    print("  Длительность (сек): avg=%d  min=%d  max=%d" % (
        round(statistics.mean(durations)), round(min(durations)), round(max(durations))
    ))
print("  Реплик за сессию:   avg=%.1f  min=%d  max=%d" % (
    statistics.mean(reply_counts), min(reply_counts), max(reply_counts)
))

ri_vals = [session_ri([t[0].get('reply','') for t in sess]) for sess in sessions if len(sess) >= 2]
if ri_vals:
    print("  RI (Jaccard биграмм): avg=%.4f  min=%.4f  max=%.4f" % (
        statistics.mean(ri_vals), min(ri_vals), max(ri_vals)
    ))
    print("  Интерпретация: 0 = нет повторов, 1 = идентичные реплики")
