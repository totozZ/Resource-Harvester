from __future__ import annotations

import html
import json
import math
import xml.etree.ElementTree as ET
from collections.abc import Iterable


def _srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def subtitle_json_to_srt(payload: dict) -> str:
    entries = payload.get("body") or []
    blocks: list[str] = []
    for index, item in enumerate(entries, start=1):
        start = float(item.get("from") or 0)
        end = max(start, float(item.get("to") or start))
        content = str(item.get("content") or "").replace("\r\n", "\n").strip()
        blocks.append(
            f"{index}\n{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n{content}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def _ass_timestamp(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, centis = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _ass_color(rgb: int) -> str:
    red = (rgb >> 16) & 0xFF
    green = (rgb >> 8) & 0xFF
    blue = rgb & 0xFF
    return f"&H{blue:02X}{green:02X}{red:02X}&"


def _ass_escape(text: str) -> str:
    return (
        html.unescape(text)
        .replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\r\n", r"\N")
        .replace("\n", r"\N")
    )


def _ass_header(width: int, height: int, font_size: int) -> str:
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Danmaku,Microsoft YaHei,{font_size},&H00FFFFFF,&H00FFFFFF,&H80000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def danmaku_xml_to_ass(
    xml_content: bytes | str,
    *,
    width: int = 1920,
    height: int = 1080,
    duration: float = 8.0,
) -> tuple[str, int]:
    root = ET.fromstring(xml_content)
    font_size = max(24, round(height / 30))
    lane_height = font_size + 8
    lane_count = max(1, math.floor((height * 0.8) / lane_height))
    top_lane = 0
    bottom_lane = 0
    scroll_lane = 0
    ignored = 0
    events: list[str] = []

    for element in root.findall(".//d"):
        fields = (element.attrib.get("p") or "").split(",")
        if len(fields) < 4:
            ignored += 1
            continue
        try:
            start = float(fields[0])
            mode = int(fields[1])
            size = max(12, int(fields[2]))
            color = int(fields[3])
        except ValueError:
            ignored += 1
            continue

        text = _ass_escape(element.text or "")
        styles = [f"\\fs{size}", f"\\c{_ass_color(color)}"]
        end = start + duration

        if mode in {1, 2, 3, 6}:
            lane = scroll_lane % lane_count
            scroll_lane += 1
            y = max(font_size, lane * lane_height + font_size)
            estimated_width = max(font_size, len(element.text or "") * size)
            if mode == 6:
                styles.append(f"\\move({-estimated_width},{y},{width},{y})")
            else:
                styles.append(f"\\move({width},{y},{-estimated_width},{y})")
        elif mode == 5:
            lane = top_lane % lane_count
            top_lane += 1
            y = lane * lane_height + font_size
            styles.extend(["\\an8", f"\\pos({width // 2},{y})"])
        elif mode == 4:
            lane = bottom_lane % lane_count
            bottom_lane += 1
            y = height - lane * lane_height - font_size
            styles.extend(["\\an2", f"\\pos({width // 2},{y})"])
        else:
            ignored += 1
            continue

        events.append(
            "Dialogue: 0,"
            f"{_ass_timestamp(start)},{_ass_timestamp(end)},Danmaku,,0,0,0,,"
            f"{{{''.join(styles)}}}{text}"
        )

    return _ass_header(width, height, font_size) + "\n".join(events) + "\n", ignored
