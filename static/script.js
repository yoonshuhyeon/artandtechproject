let myId = null;
let myNickname = "";
let myGender = "M";
let currentRoomCode = "";
let pollInterval = null;
let hasIVoted = false;

// 페이지 로드 시 기존 세션 복구 및 URL 파라미터 체크
window.addEventListener('load', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const roomFromUrl = urlParams.get('room');
    if (roomFromUrl) {
        currentRoomCode = roomFromUrl.toUpperCase();
        document.getElementById('room-code').value = currentRoomCode;
        showView('join-view');
        setTimeout(() => document.getElementById('nickname').focus(), 100);
        return;
    }
    const savedRoomCode = localStorage.getItem('atc_room_code');
    const savedNickname = localStorage.getItem('atc_nickname');
    const savedId = localStorage.getItem('atc_id');
    const savedGender = localStorage.getItem('atc_gender');
    if (savedRoomCode && savedId) {
        currentRoomCode = savedRoomCode;
        myNickname = savedNickname;
        myId = savedId;
        myGender = savedGender || "M";
        hasIVoted = localStorage.getItem('atc_has_voted') === 'true';
        checkRoomAndRestore();
    }
});

async function checkRoomAndRestore() {
    try {
        const res = await fetch(`/api/status/${currentRoomCode}`);
        const data = await res.json();
        if (data.participants && data.participants.length > 0) {
            showView('dashboard-view');
            startPolling();
        } else {
            localStorage.clear();
        }
    } catch (e) {
        localStorage.clear();
    }
}

const QUESTION_DATA = {
    'light': ["요즘 가장 빠져있는 것은?", "어릴 때 꿈은 뭐였어요?", "최근에 가장 웃겼던 일은?", "스트레스는 어떻게 푸세요?", "인생 영화나 드라마는?"],
    'deep': ["가장 소중하게 생각하는 가치관은?", "삶에서 가장 힘들었던 순간은?", "나의 가장 큰 장점과 단점은?", "10년 뒤 나의 모습은?", "사랑이란 무엇이라고 생각하세요?"],
    'fun': ["내가 만약 투명인간이 된다면?", "로또 1등 되면 가장 먼저 하고 싶은 것?", "무인도에 가져갈 세 가지?", "어제 밤에 꾼 꿈 이야기", "자신만의 특이한 습관"]
};
const GAME_CARDS = ["연애에서 가장 중요하다고 생각하는 것은?", "상대방의 첫인상은 어땠나요?", "나만 아는 맛집이 있다면?", "최근에 가장 즐겨 듣는 노래는?", "자신만의 스트레스 해소법은?"];
let currentGameCardIndex = 0;

function showView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
    document.getElementById(viewId).classList.remove('hidden');
    if (viewId === 'question-view') loadQuestions('light', document.querySelector('#question-view .tab-item'));
}

function setGender(gender, element) {
    myGender = gender;
    element.parentElement.querySelectorAll('.tab-item').forEach(t => t.classList.remove('active'));
    element.classList.add('active');
}

document.getElementById('join-btn').addEventListener('click', async () => {
    currentRoomCode = document.getElementById('room-code').value.trim().toUpperCase();
    myNickname = document.getElementById('nickname').value.trim();
    if (!currentRoomCode || !myNickname) { alert("룸 코드와 닉네임을 입력해주세요!"); return; }
    try {
        const res = await fetch(`/api/join/${currentRoomCode}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nickname: myNickname, gender: myGender })
        });
        if (!res.ok) { const err = await res.json(); alert(err.detail || "입장에 실패했습니다."); return; }
        const data = await res.json();
        myId = data.client_id;
        localStorage.setItem('atc_room_code', currentRoomCode);
        localStorage.setItem('atc_nickname', myNickname);
        localStorage.setItem('atc_id', myId);
        localStorage.setItem('atc_gender', myGender);
        showView('match-confirm-view');
        startPolling();
    } catch (e) { alert("서버 연결에 실패했습니다."); }
});

async function createRoom() {
    const code = document.getElementById('create-room-code').value.trim().toUpperCase();
    const targetCount = document.getElementById('create-target-count').value;
    const location = document.getElementById('create-location').value.trim();
    const time = document.getElementById('create-time').value.trim();
    const reservation = document.getElementById('create-reservation').value.trim();
    const nickname = document.getElementById('create-nickname').value.trim();
    if (!location || !time || !nickname) { alert("필수 정보를 입력해주세요!"); return; }
    try {
        const res = await fetch('/api/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ room_code: code, target_count: targetCount, location: location, meeting_time: time, reservation_name: reservation })
        });
        if (!res.ok) { const err = await res.json(); alert(err.detail || "방 생성에 실패했습니다."); return; }
        const data = await res.json();
        currentRoomCode = data.room_code;
        myNickname = nickname;
        const joinRes = await fetch(`/api/join/${currentRoomCode}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nickname: myNickname, gender: myGender })
        });
        const joinData = await joinRes.json();
        myId = joinData.client_id;
        localStorage.setItem('atc_room_code', currentRoomCode);
        localStorage.setItem('atc_nickname', myNickname);
        localStorage.setItem('atc_id', myId);
        localStorage.setItem('atc_gender', myGender);
        showView('match-confirm-view');
        startPolling();
    } catch (e) { alert("서버 연결에 실패했습니다."); }
}

function renderMatchingUI(data) {
    const votingArea = document.getElementById('matching-voting-area');
    const resultArea = document.getElementById('matching-result-area');
    const participantList = document.getElementById('participant-list');
    const votedWaitingMsg = document.getElementById('voted-waiting-msg');
    const voteProgress = document.getElementById('vote-progress');
    if (!votingArea) return;
    if (data && data.result && data.result !== "ROOM_DELETED") {
        votingArea.classList.add('hidden');
        resultArea.classList.remove('hidden');
        document.getElementById('matching-result-display').innerText = data.result;
        return;
    }
    resultArea.classList.add('hidden');
    votingArea.classList.remove('hidden');
    if (hasIVoted) {
        participantList.classList.add('hidden');
        votedWaitingMsg.classList.remove('hidden');
        if (data && data.participants) {
            voteProgress.innerText = `현재 참여 인원: ${data.participants.length}명 / 목표: ${data.target_count || '?'}명`;
        }
    } else {
        participantList.classList.remove('hidden');
        votedWaitingMsg.classList.add('hidden');
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/status/${currentRoomCode}`);
            const data = await res.json();
            if (data.result === "ROOM_DELETED") {
                alert("방장이 방을 폭파(삭제)했습니다.");
                localStorage.clear();
                location.reload();
                return;
            }
            if (myId && data.participants && !data.participants.find(p => p.id === myId)) {
                alert("방장에 의해 방에서 퇴장 처리되었습니다.");
                localStorage.clear();
                location.reload();
                return;
            }
            // 방장 전용 메뉴 표시
            if (myId === data.host_id) {
                document.getElementById('host-only-settings').classList.remove('hidden');
            } else {
                document.getElementById('host-only-settings').classList.add('hidden');
            }
            updateParticipantList(data.participants, data.host_id);
            renderMatchingUI(data);
            if (data.location) document.getElementById('display-location').innerText = data.location;
            if (data.meeting_time) document.getElementById('display-time').innerText = data.meeting_time;
            document.getElementById('display-reservation').innerText = data.reservation_name || "-";
            document.getElementById('display-m-count').innerText = `${data.m_count}명`;
            document.getElementById('display-f-count').innerText = `${data.f_count}명`;
            if (document.querySelector('.display-room-code')) {
                document.querySelectorAll('.display-room-code').forEach(el => el.innerText = currentRoomCode);
                const qrImg = document.getElementById('qrcode-img');
                if (qrImg && !qrImg.src.includes('qrserver')) {
                    const inviteUrl = `${window.location.origin}/?room=${currentRoomCode}`;
                    qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(inviteUrl)}`;
                }
            }
        } catch (e) { console.error("Polling error", e); }
    }, 2000);
}

async function selectPartner(targetId, cardElement) {
    if (hasIVoted) return;
    try {
        const res = await fetch(`/api/pick/${currentRoomCode}/${myId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_id: targetId })
        });
        if (res.ok) {
            hasIVoted = true;
            localStorage.setItem('atc_has_voted', 'true');
            renderMatchingUI();
        }
    } catch (e) { alert("투표 전송 실패"); }
}

function updateParticipantList(participants, hostId) {
    const listContainer = document.getElementById('participant-list');
    const waitMsg = document.getElementById('wait-msg');
    if (!listContainer) return;
    listContainer.innerHTML = "";
    const opponents = participants.filter(p => p.gender !== myGender);
    const isHost = (myId === hostId);
    if (opponents.length === 0) {
        waitMsg.classList.remove('hidden');
    } else {
        waitMsg.classList.add('hidden');
        opponents.forEach(p => {
            const card = document.createElement('div');
            card.className = "menu-card";
            card.style.flexDirection = "column";
            card.style.position = "relative";
            let kickBtnHtml = "";
            if (isHost) kickBtnHtml = `<div onclick="event.stopPropagation(); kickMember('${p.id}')" style="position:absolute; top:5px; right:10px; color:#FF528F; font-size:18px; font-weight:bold; cursor:pointer;">×</div>`;
            card.innerHTML = `${kickBtnHtml}<div class="menu-icon" style="margin-right:0; margin-bottom:10px;">👤</div><div class="menu-title">${p.name}</div>`;
            card.onclick = () => selectPartner(p.id, card);
            listContainer.appendChild(card);
        });
    }
}

async function kickMember(targetId) {
    if (!confirm("해당 멤버를 내보내시겠습니까?")) return;
    try {
        const res = await fetch(`/api/kick/${currentRoomCode}/${myId}/${targetId}`, { method: 'DELETE' });
        if (!res.ok) { const err = await res.json(); alert(err.detail || "실패"); }
    } catch (e) { alert("서버 연결 실패"); }
}

async function deleteRoom() {
    if (!confirm("정말 방을 폭파(삭제)하시겠습니까? 모든 참가자가 튕겨나갑니다.")) return;
    try {
        const res = await fetch(`/api/room/${currentRoomCode}/${myId}`, { method: 'DELETE' });
        if (res.ok) {
            alert("방이 삭제되었습니다.");
            localStorage.clear();
            location.reload();
        } else {
            const err = await res.json();
            alert(err.detail || "방 삭제 실패");
        }
    } catch (e) { alert("서버 연결 실패"); }
}

async function resetMatching() {
    if (!confirm("다시 투표를 시작할까요?")) return;
    try {
        await fetch(`/api/reset-matching/${currentRoomCode}`, { method: 'POST' });
        hasIVoted = false;
        localStorage.removeItem('atc_has_voted');
        renderMatchingUI();
    } catch (e) { alert("초기화 실패"); }
}

function loadQuestions(category, element) {
    const container = document.getElementById('question-list-container');
    if (!container) return;
    // 탭 활성화 처리
    if (element) {
        element.parentElement.querySelectorAll('.tab-item').forEach(t => t.classList.remove('active'));
        element.classList.add('active');
    }
    container.innerHTML = QUESTION_DATA[category].map(q => `<div class="q-card" onclick="selectItem(this)">${q}</div>`).join('');
}

function selectItem(element) {
    element.parentElement.querySelectorAll('.q-card').forEach(c => { c.style.borderColor = "#F0F0F0"; c.style.background = "#FDFDFD"; });
    element.style.borderColor = "var(--primary-pink)";
    element.style.background = "#FFF5F8";
}

window.nextGameCard = () => { currentGameCardIndex = (currentGameCardIndex + 1) % GAME_CARDS.length; document.querySelector('.game-card-item').innerText = GAME_CARDS[currentGameCardIndex]; };
window.prevGameCard = () => { currentGameCardIndex = (currentGameCardIndex - 1 + GAME_CARDS.length) % GAME_CARDS.length; document.querySelector('.game-card-item').innerText = GAME_CARDS[currentGameCardIndex]; };
window.sendRequest = (type) => { alert(`${type} 요청을 보냈습니다.`); showView('dashboard-view'); };
window.clearSession = () => { if (confirm("정말 나가시겠습니까?")) { localStorage.clear(); location.reload(); } };
window.copyInviteLink = () => {
    const inviteUrl = `${window.location.origin}/?room=${currentRoomCode}`;
    navigator.clipboard.writeText(inviteUrl).then(() => alert("초대 링크가 복사되었습니다!"));
};
document.getElementById('close-modal-btn').onclick = () => document.getElementById('result-modal').classList.add('hidden');
