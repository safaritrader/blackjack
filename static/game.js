const socket = io();
const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");

const tableId = "table1";
const playerId = "P" + Math.floor(Math.random() * 9999);

let tableState = null;
let bettingSeconds = 0;
let turnSeconds = 0;
let activeTurnPlayer = null;

const CARD_W = 60;
const CARD_H = 90;
const cardImages = {};
let cardsReady = false;

// ================= CANVAS =================
let assetsReady = false;
let assetsLoadingText = "Loading assets...";

let assetRetryCount = 0;
const MAX_ASSET_RETRIES = 5;
let failedCards = [];
let failedSounds = [];

const sounds = {
    bet: new Audio("/static/sounds/bet.mp3"),
    card: new Audio("/static/sounds/card.mp3"),
    win: new Audio("/static/sounds/win.mp3"),
    lose: new Audio("/static/sounds/lose.mp3")
};
// Preload images and sounds
function preloadAssets() {
    failedCards = [];
    failedSounds = [];

    const promises = [];
    const suits = ["H", "D", "C", "S"];

    // -------- Cards --------
    for (let s of suits) {
        for (let v = 1; v <= 13; v++) {
            const key = `${v}${s}`;

            // skip already loaded cards
            if (cardImages[key]?.complete && cardImages[key].naturalWidth) {
                continue;
            }

            const img = new Image();
            cardImages[key] = img;

            promises.push(new Promise((resolve, reject) => {
                img.onload = resolve;
                img.onerror = () => {
                    failedCards.push(key);
                    reject(key);
                };
                img.src = `/static/cards/${key}.png?retry=${assetRetryCount}`;
            }));
        }
    }

    // -------- Sounds --------
    Object.entries(sounds).forEach(([name, audio]) => {
        promises.push(new Promise((resolve, reject) => {
            audio.oncanplaythrough = resolve;
            audio.onerror = () => {
                failedSounds.push(name);
                reject(name);
            };
            audio.load();
        }));
    });

    return Promise.all(promises)
        .then(() => {
            assetsReady = true;
            cardsReady = true;
            console.log("All assets loaded");
        })
        .catch(() => {
            assetRetryCount++;
            assetsReady = false;

            if (assetRetryCount >= MAX_ASSET_RETRIES) {
                assetsLoadingText = "Failed to load assets. Please refresh.";
                console.error("Asset loading failed permanently");
                return;
            }

            assetsLoadingText =
                `Loading assets... retry ${assetRetryCount}/${MAX_ASSET_RETRIES}`;

            console.warn("Retrying assets:", failedCards, failedSounds);

            setTimeout(preloadAssets, 1000);
        });
}

const LOGICAL_WIDTH = 900;
const LOGICAL_HEIGHT = 600;

function resizeCanvas() {
    const container = canvas.parentElement;
    const dpr = window.devicePixelRatio || 1;

    const scale = Math.min(
        container.clientWidth / LOGICAL_WIDTH,
        container.clientHeight / LOGICAL_HEIGHT
    );

    canvas.width = LOGICAL_WIDTH * scale * dpr;
    canvas.height = LOGICAL_HEIGHT * scale * dpr;

    canvas.style.width = LOGICAL_WIDTH * scale + "px";
    canvas.style.height = LOGICAL_HEIGHT * scale + "px";

    ctx.setTransform(
        scale * dpr,
        0,
        0,
        scale * dpr,
        0,
        0
    );

    draw();
}


resizeCanvas();
window.addEventListener("resize", resizeCanvas);

// ================= RESET =================
function resetVisualRound() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    activeTurnPlayer = null;
    turnSeconds = 0;
    bettingSeconds = 0;
}

// ================= CARD LOADER =================
function loadCards() {
    const suits = ["H", "D", "C", "S"];
    const promises = [];

    for (let s of suits) {
        for (let v = 1; v <= 13; v++) {
            const key = `${v}${s}`;
            const img = new Image();

            const p = new Promise(resolve => {
                img.onload = resolve;
                img.onerror = () => {
                    console.warn("Missing card image:", key);
                    resolve();
                };
            });

            img.src = `/static/cards/${key}.png`;
            cardImages[key] = img;
            promises.push(p);
        }
    }

    return Promise.all(promises).then(() => {
        cardsReady = true;
        console.log("All cards loaded");
        draw();
    });
}

loadCards();

// ================= SOCKET =================

preloadAssets();

const waitForAssets = setInterval(() => {
    if (assetsReady && cardsReady) {
        clearInterval(waitForAssets);
        socket.emit("join", { table: tableId, player: playerId });
        draw();
    }
}, 100);


socket.on("betting_timer", d => {
    bettingSeconds = d.seconds;
    draw();
});

socket.on("player_timer", d => {
    activeTurnPlayer = d.player;
    turnSeconds = d.seconds;
    draw();
});

socket.on("table_state", d => {
    tableState = d;
    playSound("card");
    console.log(tableState);
    console.log('stats recived');
    draw();
});

socket.on("round_end", d => {
    activeTurnPlayer = null;
    turnSeconds = 0;

    Object.values(d.results || {}).flat().forEach(h => {
        playSound(h.win > 0 ? "win" : h.win < 0 ? "lose" : null);
    });

    tableState = { ...tableState, dealer: d.dealer };
    draw();

    setTimeout(() => {
        resetVisualRound();
        draw();
    }, 2000);
});

// ================= USER =================
function bet() {
    const amount = parseInt(document.getElementById("bet").value);
    socket.emit("bet", { table: tableId, player: playerId, amount });

    if (tableState?.bets) {
        tableState.bets[playerId] =
            (tableState.bets[playerId] || 0) + amount;
    }

    playSound("bet");
    draw();
}

function action(type) {
    socket.emit("action", { table: tableId, player: playerId, action: type });
}

// ================= DRAW =================
function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "white";
    ctx.font = `16px Arial`;
    if (!assetsReady) {
        ctx.fillText(assetsLoadingText, 360, 300);
        return;
    }
    if (!cardsReady) {
        ctx.fillText("Loading cards...", 360, 300);
        return;
    }

    if (bettingSeconds > 0) {
        ctx.fillText(`BETTING: ${bettingSeconds}`, 400, 40);
    }

    if (!tableState) return;

    console.log('draw');
    console.log(tableState);
    drawSeats();
    drawDealer();
    drawPlayers();
    drawTurnIndicator();
}


function drawSeats() {
    const seatW = 100 ;
    const seatH = 30 ;

    for (let i = 0; i < 5; i++) {
        const pid = tableState.player_order[i];
        const x = (100 + i * 150) ;
        const y = 420 ;

        if (pid === activeTurnPlayer) {
            ctx.fillStyle = "rgba(255,215,0,0.4)";
            ctx.fillRect(x - 5, y - 5, seatW + 10, seatH + 10);
        }

        ctx.strokeStyle = "white";
        ctx.strokeRect(x, y, seatW, seatH);

        ctx.fillStyle = "white";
        ctx.fillText(pid || "EMPTY", x + 10, y + 20);
    }
}


function drawDealer() {
    ctx.fillStyle = "white";
    ctx.font = "16px Arial";

    ctx.fillText("DEALER", 400, 60);

    if (!tableState.dealer) return;

    tableState.dealer.forEach((c, i) => {
        drawCard(c, 350 + i * 70, 80);
    });

    ctx.fillText(
        "Total: " + handValue(tableState.dealer),
        350,
        190
    );
}

function drawPlayers() {
    ctx.font = "14px Arial";

    tableState.player_order.forEach((pid, idx) => {
        const p = tableState.players[pid];
        if (!p) return;

        const baseX = 100 + idx * 150;
        const baseY = 350;

        ctx.fillStyle = "white";
        ctx.fillText(pid, baseX, 520);
        ctx.fillText("Chips: " + p.chips, baseX, 540);

        if (tableState.bets?.[pid]) {
            ctx.fillStyle = "lime";
            ctx.fillText("Bet: " + tableState.bets[pid], baseX, 560);
        }

        p.hands?.forEach((hand, h) => {
            const y = baseY - h * 120;

            hand.forEach((c, i) => {
                drawCard(c, baseX + i * 30, y);
            });

            ctx.fillStyle = "white";
            ctx.fillText(handValue(hand), baseX, y - 10);
        });
    });
}

function drawTurnIndicator() {
    if (!activeTurnPlayer) return;

    ctx.fillStyle = "yellow";
    ctx.font = "18px Arial";

    ctx.fillText(
        `TURN: ${activeTurnPlayer} (${turnSeconds}s)`,
        350,
        580
    );

    if (activeTurnPlayer === playerId) {
        ctx.font = "20px Arial";
        ctx.fillText("YOUR TURN", 380, 560);
    }
}


// ================= CARD =================
function drawCard(card, x, y) {
    const img = cardImages[card];

    if (!img || !img.complete || !img.naturalWidth) {
        ctx.fillStyle = "#444";
        ctx.fillRect(x, y, CARD_W, CARD_H);
        ctx.strokeStyle = "white";
        ctx.strokeRect(x, y, CARD_W, CARD_H);
        action('error_loading_cards');
        return;
    }
    ctx.drawImage(img, x, y, CARD_W, CARD_H);
}

// ================= UTILS =================
function handValue(hand) {
    let total = 0, aces = 0;
    hand.forEach(c => {
        const v = parseInt(c);
        total += Math.min(v, 10);
        if (v === 1) aces++;
    });
    while (aces && total <= 11) {
        total += 10;
        aces--;
    }
    return total;
}

// ================= SOUNDS =================


function playSound(name) {
    const s = sounds[name];
    if (!s) return;
    s.currentTime = 0;
    s.play();
}
