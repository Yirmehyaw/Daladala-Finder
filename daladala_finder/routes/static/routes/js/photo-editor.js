// Profile photo editor (profile page).
// After choosing a picture, the person fits it in the circle (drag, zoom, pinch), rotates or
// flips it and adjusts brightness, contrast and colour. Only the finished square picture is
// uploaded; the server still checks it and removes hidden data (see accounts/photos.py).
// No libraries needed. Without JavaScript the picture uploads straight away as before.
(() => {
  const dialog = document.getElementById("photo-editor");
  const form = document.getElementById("photo-form");
  const input = document.getElementById("id_photo");
  if (!dialog || !form || !input) return;

  // Old browsers without <dialog>: upload straight away
  if (typeof dialog.showModal !== "function") {
    input.addEventListener("change", () => { if (input.files.length) form.submit(); });
    return;
  }

  const canvas = dialog.querySelector(".pe-canvas");
  const ctx = canvas.getContext("2d");
  const errorBox = dialog.querySelector(".pe-error");
  const saveBtn = dialog.querySelector('[data-pe-action="save"]');
  const zoomInput = dialog.querySelector('[data-pe="zoom"]');
  const sliders = dialog.querySelectorAll("[data-pe]");
  const VIEW = canvas.width;      // preview size (canvas pixels)
  const OUT = 800;                // uploaded picture size; the server makes it 400 x 400
  const MAX_ZOOM = 4;

  // Brightness etc. need canvas filters (all current browsers). Hide the sliders if missing.
  if (typeof ctx.filter !== "string") dialog.querySelector(".pe-adjust").hidden = true;

  let img = null;
  let objectUrl = null;
  let s;                          // editor state, see reset()

  function reset() {
    s = { zoom: 1, x: 0, y: 0, rotate: 0, flip: false, brightness: 100, contrast: 100, saturate: 100 };
    sliders.forEach((el) => { el.value = s[el.dataset.pe]; });
    clamp();
    draw();
  }

  // Size of the (rotated) picture on the preview at the current zoom
  function shownSize() {
    const turned = s.rotate % 180 !== 0;
    const w = turned ? img.naturalHeight : img.naturalWidth;
    const h = turned ? img.naturalWidth : img.naturalHeight;
    const cover = Math.max(VIEW / w, VIEW / h);   // zoom 1 = picture just fills the square
    return { w: w * cover * s.zoom, h: h * cover * s.zoom, scale: cover * s.zoom };
  }

  // Never let an empty edge show inside the square
  function clamp() {
    if (!img) return;
    const { w, h } = shownSize();
    const maxX = Math.max(0, (w - VIEW) / 2);
    const maxY = Math.max(0, (h - VIEW) / 2);
    s.x = Math.min(maxX, Math.max(-maxX, s.x));
    s.y = Math.min(maxY, Math.max(-maxY, s.y));
  }

  // Draw the picture on any canvas; size = that canvas's width (preview or upload)
  function paint(target, size) {
    const k = size / VIEW;
    const { scale } = shownSize();
    const c = target.getContext("2d");
    c.save();
    c.fillStyle = "#fff";
    c.fillRect(0, 0, size, size);
    if (typeof c.filter === "string") {
      c.filter = `brightness(${s.brightness}%) contrast(${s.contrast}%) saturate(${s.saturate}%)`;
    }
    c.imageSmoothingQuality = "high";
    c.translate(size / 2 + s.x * k, size / 2 + s.y * k);
    if (s.flip) c.scale(-1, 1);
    c.rotate((s.rotate * Math.PI) / 180);
    const w = img.naturalWidth * scale * k;
    const h = img.naturalHeight * scale * k;
    c.drawImage(img, -w / 2, -h / 2, w, h);
    c.restore();
  }

  let frame = 0;
  function draw() {
    if (!img || frame) return;
    frame = requestAnimationFrame(() => { frame = 0; paint(canvas, VIEW); });
  }

  function setZoom(value) {
    const next = Math.min(MAX_ZOOM, Math.max(1, value));
    const ratio = next / s.zoom;
    s.x *= ratio;                 // keep the middle of the circle on the same spot
    s.y *= ratio;
    s.zoom = next;
    zoomInput.value = next;
    clamp();
    draw();
  }

  // ---------- open / close ----------
  function open(src) {
    img = null;
    errorBox.hidden = true;
    saveBtn.disabled = true;
    ctx.clearRect(0, 0, VIEW, VIEW);
    const picture = new Image();
    picture.onload = () => {
      img = picture;
      saveBtn.disabled = false;
      reset();
    };
    picture.onerror = () => { errorBox.hidden = false; };
    picture.src = src;
    dialog.showModal();
    canvas.focus();
  }

  input.addEventListener("change", () => {
    const file = input.files[0];
    if (!file) return;
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(file);
    open(objectUrl);
  });

  // "Adjust photo": edit the photo already saved
  document.querySelectorAll("[data-edit-photo]").forEach((btn) => {
    btn.hidden = false;
    btn.addEventListener("click", () => open(btn.dataset.editPhoto));
  });

  dialog.addEventListener("close", () => {
    if (form.classList.contains("is-uploading")) return;
    input.value = "";             // so choosing the same file again opens the editor again
    if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
  });

  // ---------- controls ----------
  sliders.forEach((el) => {
    el.addEventListener("input", () => {
      if (!img) return;
      if (el.dataset.pe === "zoom") return setZoom(Number(el.value));
      s[el.dataset.pe] = Number(el.value);
      draw();
    });
  });

  dialog.addEventListener("click", (e) => {
    const action = e.target.closest("[data-pe-action]")?.dataset.peAction;
    if (!action || !img) return;
    if (action === "rotate-left" || action === "rotate-right") {
      // A flipped picture turns the other way, so swap the direction to match the button
      const right = (action === "rotate-right") !== s.flip;
      s.rotate = (s.rotate + (right ? 90 : 270)) % 360;
      [s.x, s.y] = action === "rotate-right" ? [-s.y, s.x] : [s.y, -s.x];
      clamp();
      draw();
    } else if (action === "flip") {
      s.flip = !s.flip;
      s.x = -s.x;
      draw();
    } else if (action === "reset") {
      reset();
    } else if (action === "save") {
      save();
    }
  });

  // Drag with mouse or finger; pinch with two fingers
  const pointers = new Map();
  let pinch = null;
  const toCanvas = () => VIEW / canvas.getBoundingClientRect().width;

  canvas.addEventListener("pointerdown", (e) => {
    if (!img) return;
    canvas.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = { dist: Math.hypot(a.x - b.x, a.y - b.y), zoom: s.zoom };
    }
  });
  canvas.addEventListener("pointermove", (e) => {
    const last = pointers.get(e.pointerId);
    if (!last) return;
    const now = { x: e.clientX, y: e.clientY };
    pointers.set(e.pointerId, now);
    if (pointers.size === 2 && pinch) {
      const [a, b] = [...pointers.values()];
      setZoom(pinch.zoom * (Math.hypot(a.x - b.x, a.y - b.y) / pinch.dist));
    } else if (pointers.size === 1) {
      const f = toCanvas();
      s.x += (now.x - last.x) * f;
      s.y += (now.y - last.y) * f;
      clamp();
      draw();
    }
  });
  const release = (e) => {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
  };
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointercancel", release);

  canvas.addEventListener("wheel", (e) => {
    if (!img) return;
    e.preventDefault();
    setZoom(s.zoom * Math.exp(-e.deltaY * 0.0015));
  }, { passive: false });

  canvas.addEventListener("keydown", (e) => {
    if (!img) return;
    const step = e.shiftKey ? 40 : 10;
    const moves = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
    if (moves[e.key]) {
      s.x += moves[e.key][0];
      s.y += moves[e.key][1];
      clamp();
      draw();
    } else if (e.key === "+" || e.key === "=") {
      setZoom(s.zoom * 1.1);
    } else if (e.key === "-" || e.key === "_") {
      setZoom(s.zoom / 1.1);
    } else {
      return;
    }
    e.preventDefault();
  });

  // ---------- save: make the square picture and send it with the normal form ----------
  function save() {
    const out = document.createElement("canvas");
    out.width = out.height = OUT;
    paint(out, OUT);
    out.toBlob((blob) => {
      if (!blob) return;
      const file = new File([blob], "photo.jpg", { type: "image/jpeg" });
      form.classList.add("is-uploading");
      dialog.classList.add("is-uploading");
      saveBtn.disabled = true;
      try {
        const files = new DataTransfer();
        files.items.add(file);
        input.files = files.files;
        form.submit();            // normal post: the page reloads with "Profile photo saved."
      } catch {
        // Very old browsers cannot set a file input: send it in the background instead
        const data = new FormData(form);
        data.set("photo", file);
        fetch(form.action, { method: "POST", body: data, credentials: "same-origin" })
          .then(() => window.location.reload());
      }
    }, "image/jpeg", 0.92);
  }
})();
