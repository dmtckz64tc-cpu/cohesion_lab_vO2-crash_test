// game.js_v4
// POC v0.1 — joueur + bille d'inertie

const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");

canvas.width = window.innerWidth;
canvas.height = window.innerHeight;


// --------------------------------------------------
// MONDE
// --------------------------------------------------

const world = {
    cx: canvas.width / 2,
    cy: canvas.height / 2,

    // rayon de la zone centrale
    coreRadius: 45,

    // accélération maximale vers le centre
    maxAcceleration: 0.12,

    // distance maximale avant décrochage
    maxCouplingDistance: 180
};


// --------------------------------------------------
// JOUEUR
// --------------------------------------------------

const player = {
    x: canvas.width / 2 + 220,
    y: canvas.height / 2,

    vx: 0,
    vy: 0,

    radius: 10,

    // force produite par l'input
    thrust: 0.35
};


// --------------------------------------------------
// BILLE D'INERTIE
// --------------------------------------------------

const ball = {
    x: player.x + 60,
    y: player.y,

    vx: 0,
    vy: 0,

    radius: 14,

    inertia: 0.985
};



// --------------------------------------------------
// CAMÉRA
// --------------------------------------------------

const camera = {
    x: ball.x,
    y: ball.y,

    zoom: 80,

    minZoom: 0.7,
    maxZoom: 2.5
};

// --------------------------------------------------
// INPUT
// --------------------------------------------------

const keys = {};

window.addEventListener("keydown", e => {
    keys[e.key] = true;
});

window.addEventListener("keyup", e => {
    keys[e.key] = false;
});


// --------------------------------------------------
// PHYSIQUE
// --------------------------------------------------

function update() {

    // ----- direction donnée par le joueur -----

    let ax = 0;
    let ay = 0;

    if (keys["ArrowLeft"])  ax -= player.thrust;
    if (keys["ArrowRight"]) ax += player.thrust;
    if (keys["ArrowUp"])    ay -= player.thrust;
    if (keys["ArrowDown"])  ay += player.thrust;

    player.vx += ax;
    player.vy += ay;


    // ----- attraction vers le centre -----

    const dx = world.cx - player.x;
    const dy = world.cy - player.y;

    const distance = Math.hypot(dx, dy);

    if (distance > world.coreRadius) {

        const nx = dx / distance;
        const ny = dy / distance;

        const force =
            Math.min(
                world.maxAcceleration,
                distance * 0.0008
            );

        player.vx += nx * force;
        player.vy += ny * force;
    }


    // ----- déplacement joueur -----

    player.x += player.vx;
    player.y += player.vy;

    // ----- distance au centre -----
    const centerDistance = Math.hypot(
    ball.x - world.cx,
    ball.y - world.cy
    );

    const centerRatio =
    Math.min(
        1,
        centerDistance / 100
    );

    ball.inertia =
    0.92 + centerRatio * 0.075;

    // ----- bille : inertie -----

    ball.vx *= ball.inertia;
    ball.vy *= ball.inertia;

    ball.x += ball.vx;
    ball.y += ball.vy;


    // ----- couplage joueur / bille -----

    const bx = player.x - ball.x;
    const by = player.y - ball.y;

    const couplingDistance = Math.hypot(bx, by);

    if (couplingDistance > 0) {

        // la bille commence à suivre le joueur
        // lorsque celui-ci s'éloigne

        const couplingStrength =
            Math.min(0.08, couplingDistance * 0.0005);

        ball.vx += bx * couplingStrength;
        ball.vy += by * couplingStrength;
    }



}

function updateCamera() {

    camera.x = ball.x;
    camera.y = ball.y;

    const dx = player.x - ball.x;
    const dy = player.y - ball.y;

    const distance = Math.hypot(dx, dy);

    const zoom = 2.5 - distance * 0.006;

    camera.zoom = Math.max(
        camera.minZoom,
        Math.min(camera.maxZoom, zoom)
    );
}

// --------------------------------------------------
// DESSIN
// --------------------------------------------------

function draw() {

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // ----- moving_world -----

    ctx.save();

    ctx.translate(
        canvas.width / 2,
        canvas.height / 2
    );

    ctx.scale(
        camera.zoom,
        camera.zoom
    );

    ctx.translate(
        -camera.x,
        -camera.y
    );


    // ----- objects -----

    ctx.fillStyle = "red";
    ctx.strokeStyle = "red";
    ctx.lineWidth = 3;

    // ----- centre -----

    ctx.beginPath();
    ctx.arc(
        world.cx,
        world.cy,
        world.coreRadius,
        0,
        Math.PI * 2
    );

    ctx.stroke();


    // ----- lien -----

    ctx.beginPath();
    ctx.moveTo(player.x, player.y);
    ctx.lineTo(ball.x, ball.y);
    ctx.stroke();


    // ----- bille -----

    ctx.beginPath();
    ctx.arc(
        ball.x,
        ball.y,
        ball.radius,
        0,
        Math.PI * 2
    );

    ctx.fill();


    // ----- joueur -----

    ctx.beginPath();
    ctx.arc(
        player.x,
        player.y,
        player.radius,
        0,
        Math.PI * 2
    );

    ctx.fill();



    // ----- distance de couplage -----

    const d = Math.hypot(
        player.x - ball.x,
        player.y - ball.y
    );

    ctx.fillText(
        "couplage : " + Math.round(d),
        20,
        30
    );


    ctx.restore();
}


// --------------------------------------------------
// BOUCLE
// --------------------------------------------------

function loop() {

    update();
    updateCamera();
    draw();

    requestAnimationFrame(loop);
}

loop();

