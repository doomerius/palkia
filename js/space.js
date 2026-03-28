// Shared space canvas + cursor for non-homepage pages
const cursor = document.getElementById('cursor');
const ring = document.getElementById('cursor-ring');
if (cursor && ring) {
  let mx = 0, my = 0, rx = 0, ry = 0;
  document.addEventListener('mousemove', e => {
    mx = e.clientX; my = e.clientY;
    cursor.style.left = mx + 'px';
    cursor.style.top = my + 'px';
  });
  function animateRing() {
    rx += (mx - rx) * 0.12;
    ry += (my - ry) * 0.12;
    ring.style.left = rx + 'px';
    ring.style.top = ry + 'px';
    requestAnimationFrame(animateRing);
  }
  animateRing();
}

const canvas = document.getElementById('space-canvas');
if (canvas) {
  const ctx = canvas.getContext('2d');
  let W, H, particles = [];

  function resize() { W = canvas.width = window.innerWidth; H = canvas.height = window.innerHeight; }

  class Particle {
    constructor() { this.reset(); }
    reset() {
      this.x = Math.random() * W;
      this.y = Math.random() * H;
      this.r = Math.random() * 1.5 + 0.3;
      this.alpha = Math.random() * 0.4 + 0.05;
      this.hue = Math.random() * 60 + 260;
      this.phase = Math.random() * Math.PI * 2;
      this.speed = Math.random() * 0.008 + 0.003;
      this.vx = (Math.random() - 0.5) * 0.15;
      this.vy = (Math.random() - 0.5) * 0.15;
    }
    update() {
      this.x += this.vx;
      this.y += this.vy;
      this.phase += this.speed;
      if (this.x < 0 || this.x > W || this.y < 0 || this.y > H) this.reset();
    }
    draw() {
      const p = Math.sin(this.phase) * 0.4 + 0.6;
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.r * p, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${this.hue}, 70%, 70%, ${this.alpha * p})`;
      ctx.fill();
    }
  }

  resize();
  particles = Array.from({length: 120}, () => new Particle());
  window.addEventListener('resize', resize);

  function loop() {
    ctx.fillStyle = 'rgba(2,2,10,0.15)';
    ctx.fillRect(0, 0, W, H);
    particles.forEach(p => { p.update(); p.draw(); });
    requestAnimationFrame(loop);
  }
  loop();
}
