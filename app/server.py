from __future__ import annotations

import asyncio
import random
import time
import uuid
import os
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

# ==========================================
# 질문 데이터 (prompts.py 내용 통합)
# ==========================================
PROMPTS: list[str] = [
    "밸런스 게임: 애인 연락 빈도 (하루 1번 vs 틈날 때마다)",
    "지금 이 자리에서 한 명만 초능력 얻는다면 누구? 이유는 10초 제한",
    "밸런스 게임: 첫 데이트 (조용한 카페 vs 시끌벅적 포차)",
    "가장 최근에 소소하게 행복했던 순간은? (30초 안에)",
    "오늘 서로 별명 하나씩 지어주기 (상대가 싫으면 즉시 거절 가능)",
    "인생 영화나 드라마 하나씩 추천하고 이유 말하기",
    "스트레스 해소법 공유하기! (운동 vs 먹기 vs 잠자기)",
    "어릴 때 꿈은 무엇이었나요? 지금은 어떤가요?",
]

# ==========================================
# 백엔드 로직
# ==========================================
app = FastAPI(title="atc-backend", version="0.1.0")

# 정적 파일 경로 설정
static_path = os.path.join(os.path.dirname(__file__), "static")
image_path = os.path.join(os.path.dirname(__file__), "앱구성")
app.mount("/static", StaticFiles(directory=static_path), name="static")
app.mount("/앱구성", StaticFiles(directory=image_path), name="앱구성")

@app.get("/")
async def read_index():
    # static 폴더 안의 index.html을 반환
    return FileResponse(os.path.join(static_path, "index.html"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@dataclass
class RoomState:
    code: str
    created_at: float = field(default_factory=lambda: time.time())
    sockets: set[WebSocket] = field(default_factory=set)
    participants: dict[str, dict] = field(default_factory=dict)
    picks: dict[str, str] = field(default_factory=dict)

ROOMS: dict[str, RoomState] = {}

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

async def broadcast(room: RoomState, message: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    for ws in list(room.sockets):
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        room.sockets.discard(ws)

@app.websocket("/ws/{room_code}")
async def ws_room(websocket: WebSocket, room_code: str) -> None:
    await websocket.accept()
    room_code = room_code.upper()
    if room_code not in ROOMS:
        ROOMS[room_code] = RoomState(code=room_code)
    
    room = ROOMS[room_code]
    client_id = uuid.uuid4().hex[:4]
    room.sockets.add(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")

            if event_type == "join":
                gender = data.get("gender", "M")
                nickname = data.get("nickname", "익명").strip()
                team = "남성" if gender == "M" else "여성"
                name = nickname if nickname else f"{team} {len(room.participants) + 1}"
                room.participants[client_id] = {"id": client_id, "team": team, "name": name, "gender": gender}
                
                await websocket.send_json({
                    "type": "state",
                    "room_code": room.code,
                    "my_id": client_id,
                    "participants": list(room.participants.values())
                })
                await broadcast(room, {"type": "presence", "participants": list(room.participants.values())})

            elif event_type == "pick":
                target_id = data.get("target_id")
                room.picks[client_id] = target_id
                await websocket.send_json({"type": "pick_confirmed", "target_id": target_id})

                if len(room.picks) >= len(room.participants) and len(room.participants) > 1:
                    males = [p for p in room.participants.values() if p['gender'] == 'M']
                    females = [p for p in room.participants.values() if p['gender'] == 'F']
                    unpaired_m_ids = {p['id'] for p in males}
                    unpaired_f_ids = {p['id'] for p in females}
                    final_pairs = []

                    # 1순위: 서로 지목
                    for f_id in list(unpaired_f_ids):
                        target_m_id = room.picks.get(f_id)
                        if target_m_id in unpaired_m_ids and room.picks.get(target_m_id) == f_id:
                            final_pairs.append((f_id, target_m_id))
                            unpaired_f_ids.remove(f_id)
                            unpaired_m_ids.remove(target_m_id)

                    # 2순위: 여성 지목 우선
                    targeted_by = {}
                    for f_id in unpaired_f_ids:
                        target_m_id = room.picks.get(f_id)
                        if target_m_id in unpaired_m_ids:
                            targeted_by.setdefault(target_m_id, []).append(f_id)
                    
                    m_ids_to_process = list(targeted_by.keys())
                    random.shuffle(m_ids_to_process)
                    for m_id in m_ids_to_process:
                        if m_id in unpaired_m_ids:
                            f_list = targeted_by[m_id]
                            chosen_f = random.choice(f_list)
                            final_pairs.append((chosen_f, m_id))
                            unpaired_f_ids.remove(chosen_f)
                            unpaired_m_ids.remove(m_id)

                    # 3순위: 랜덤
                    remaining_f, remaining_m = list(unpaired_f_ids), list(unpaired_m_ids)
                    random.shuffle(remaining_f); random.shuffle(remaining_m)
                    while remaining_f and remaining_m:
                        final_pairs.append((remaining_f.pop(), remaining_m.pop()))
                    
                    # 결과 메시지
                    prompt = random.choice(PROMPTS)
                    result_message = f"🎉 운명의 자리 배치표 발표! 🎉\n\n 오늘의 미션: {prompt}\n\n"
                    random.shuffle(final_pairs)
                    for f_id, m_id in final_pairs:
                        result_message += f"✨ {room.participants[f_id]['name']}  X  {room.participants[m_id]['name']}\n"
                    
                    if remaining_f or remaining_m:
                        result_message += "\n⚠️ 인원이 맞지 않아 일부 인원은 자리가 고정되었습니다."
                    
                    await broadcast(room, {"type": "final_result", "message": result_message})
                    room.picks.clear()
                    await broadcast(room, {"type": "pick_reset"})

    except WebSocketDisconnect:
        pass
    finally:
        room.sockets.discard(websocket)
        room.participants.pop(client_id, None)
        room.picks.pop(client_id, None)
        await broadcast(room, {"type": "presence", "participants": list(room.participants.values())})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
