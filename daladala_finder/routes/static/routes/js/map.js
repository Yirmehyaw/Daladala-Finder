// Map helper for every page of the site.
// Uses Leaflet (bundled in static/routes/vendor/leaflet) with free OpenStreetMap tiles.
// Route lines follow the real roads (paths come from the server, see services/road_paths.py).
// No API key or account needed. OpenStreetMap needs the browser to send the site address
// (see SECURE_REFERRER_POLICY in settings.py) - do not remove that setting.
//
// Pages use it like this:
//   DaladalaMap.ready(() => {
//     const map = DaladalaMap.create("map");
//     DaladalaMap.showNetwork(map, routes, stops);  // home: all routes
//     DaladalaMap.drawRoute(map, route);            // one route
//     const layer = DaladalaMap.drawLegs(map, legs); // a journey
//     layer.remove();                                // clear a journey
//   });
//
// Every map also gets a "Show my location" button (see locateControl): it follows the
// user as they move and names the nearest stop. Browsers only allow this on https
// or on http://127.0.0.1 / localhost.

// Words shown on the map. base.html fills window.DALADALA_TEXT in English or Swahili.
const MAP_TEXT = Object.assign({
  showMyLocation: "Show my location",
  youAreHere: "You are here",
  withinMetres: "within %(m)s m",
  nearestStop: "Nearest stop",
  boardHere: "Board here",
  changeHere: "Change here",
  getOff: "Get off",
  locationBlocked: "Location is blocked. Allow it for this site in your browser settings.",
  locationFailed: "Could not find your location. Try again outside or with GPS on.",
}, window.DALADALA_TEXT || {});

const DaladalaMap = {
  DAR_CENTER: [-6.80, 39.25],   // centre of Dar es Salaam
  TILES: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  FIT: { padding: [40, 40] },

  // Page code runs straight away (kept so the templates stay simple)
  ready(fn) {
    fn();
  },

  create(elementId) {
    const map = L.map(elementId, { scrollWheelZoom: false }).setView(this.DAR_CENTER, 12);
    L.tileLayer(this.TILES, {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);
    // Zoom with the mouse wheel only after the user clicks the map (so the page scrolls normally)
    map.on("click", () => map.scrollWheelZoom.enable());
    map.on("mouseout", () => map.scrollWheelZoom.disable());
    // Recalculate size after the page finishes loading so no grey gaps appear
    window.addEventListener("load", () => map.invalidateSize());
    setTimeout(() => map.invalidateSize(), 300);
    this.locateControl(map);
    return map;
  },

  // ---------- the user's own position ----------
  // Button on the map. 1st tap: start tracking and follow the user.
  // Tap while following: stop. Tap after dragging the map away: follow again.
  locateControl(map) {
    if (!("geolocation" in navigator)) return;
    const me = { watchId: null, follow: true, dot: null, ring: null, fix: null };
    const Control = L.Control.extend({
      options: { position: "topleft" },
      onAdd: () => {
        const box = L.DomUtil.create("div", "leaflet-bar");
        const btn = L.DomUtil.create("a", "locate-btn", box);
        btn.href = "#";
        btn.setAttribute("role", "button");
        btn.title = btn.ariaLabel = MAP_TEXT.showMyLocation;
        btn.innerHTML = "&#10148;";
        L.DomEvent.disableClickPropagation(box);
        L.DomEvent.on(btn, "click", (e) => {
          L.DomEvent.preventDefault(e);
          if (me.watchId === null) start(btn);
          else if (!me.follow) { me.follow = true; btn.classList.add("following"); if (me.fix) map.setView(me.fix, Math.max(map.getZoom(), 16)); }
          else stop(btn);
        });
        return box;
      },
    });

    const start = (btn) => {
      me.follow = true;
      btn.classList.add("active", "following");
      me.watchId = navigator.geolocation.watchPosition(
        (pos) => update(pos),
        (err) => {
          stop(btn);
          const why = err.code === err.PERMISSION_DENIED ? MAP_TEXT.locationBlocked : MAP_TEXT.locationFailed;
          L.popup().setLatLng(map.getCenter()).setContent(why).openOn(map);
        },
        { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 }
      );
    };

    const stop = (btn) => {
      if (me.watchId !== null) navigator.geolocation.clearWatch(me.watchId);
      me.watchId = null;
      me.fix = null;
      if (me.dot) me.dot.remove();
      if (me.ring) me.ring.remove();
      me.dot = me.ring = null;
      btn.classList.remove("active", "following");
    };

    const update = (pos) => {
      const first = !me.fix;
      me.fix = L.latLng(pos.coords.latitude, pos.coords.longitude);
      const acc = pos.coords.accuracy;
      if (!me.dot) {
        me.ring = L.circle(me.fix, { radius: acc, color: "#2563EB", weight: 1, fillOpacity: 0.12, interactive: false }).addTo(map);
        me.dot = L.marker(me.fix, {
          icon: L.divIcon({ className: "", html: '<span class="me-dot"></span>', iconSize: [20, 20], iconAnchor: [10, 10] }),
          zIndexOffset: 2000, title: MAP_TEXT.youAreHere,
        }).addTo(map);
      } else {
        me.ring.setLatLng(me.fix).setRadius(acc);
        me.dot.setLatLng(me.fix);
      }
      me.dot.bindPopup(this.whereAmI(map, me.fix, acc));
      if (first) me.dot.openPopup();
      if (me.follow) map.setView(me.fix, first ? Math.max(map.getZoom(), 16) : map.getZoom());
    };

    // Dragging the map stops following (tracking keeps going)
    map.on("dragstart", () => {
      if (me.watchId === null) return;
      me.follow = false;
      map.getContainer().querySelector(".locate-btn")?.classList.remove("following");
    });

    new Control().addTo(map);
  },

  // Popup text: "You are here" and the closest stop drawn on this map
  whereAmI(map, here, accuracy) {
    let text = "<strong>" + MAP_TEXT.youAreHere + "</strong> <small>(" +
      MAP_TEXT.withinMetres.replace("%(m)s", Math.round(accuracy)) + ")</small>";
    let best = null;
    (map._stops || []).forEach((s) => {
      const d = map.distance(here, [s.lat, s.lng]);
      if (!best || d < best.d) best = { s, d };
    });
    if (best) {
      const far = best.d < 1000 ? Math.round(best.d) + " m" : (best.d / 1000).toFixed(1) + " km";
      text += "<br>" + MAP_TEXT.nearestStop + ": " + (best.s.id
        ? '<a href="/stops/' + best.s.id + '/">' + best.s.name + "</a>"
        : best.s.name) + " (" + far + ")";
    }
    return text;
  },

  // ---------- markers ----------
  stopDot(stop, color = "#1E2A33", radius = 6) {
    return L.circleMarker([stop.lat, stop.lng], {
      radius, color: "#ffffff", weight: 2, fillColor: color, fillOpacity: 1,
    }).bindTooltip(stop.name, { direction: "top", offset: [0, -6] });
  },

  // Round labelled pin: kind = "start" (green), "end" (red) or "change" (yellow)
  pin(stop, kind, label, text) {
    const icon = L.divIcon({
      className: "",
      html: `<span class="map-pin map-pin-${kind}">${label}</span>`,
      iconSize: [30, 30],
      iconAnchor: [15, 15],
      popupAnchor: [0, -16],
    });
    return L.marker([stop.lat, stop.lng], { icon, zIndexOffset: 1000, title: text })
      .bindPopup(text);
  },

  // Write a stop's name on the map next to its marker (always visible)
  // main = true for board / change / get-off stops: their names are never hidden
  label(layer, name, side = "right", main = false) {
    layer.unbindTooltip();   // remove the hover-only label first
    return layer.bindTooltip(name, {
      permanent: true,
      direction: side,
      offset: side === "right" ? [14, 0] : [-14, 0],
      className: "stop-label" + (main ? " stop-label-main" : ""),
    });
  },

  // Hide stop names that would cover another name. Zooming in shows them again.
  declutter(map) {
    const run = () => {
      const box = map.getContainer();
      const labels = [
        ...box.querySelectorAll(".stop-label-main"),
        ...box.querySelectorAll(".stop-label:not(.stop-label-main)"),
      ];
      const placed = [];
      labels.forEach((el) => {
        el.style.visibility = "";
        const r = el.getBoundingClientRect();
        const hits = placed.some((p) =>
          r.left < p.right + 2 && r.right > p.left - 2 && r.top < p.bottom + 2 && r.bottom > p.top - 2);
        if (hits && !el.classList.contains("stop-label-main")) el.style.visibility = "hidden";
        else placed.push(r);
      });
    };
    if (!map._declutterOn) {
      map.on("zoomend moveend", run);
      map._declutterOn = true;
    }
    setTimeout(run, 50);
  },

  line(points, color, weight = 5) {
    return [
      L.polyline(points, { color: "#ffffff", weight: weight + 4, opacity: 0.9 }),
      L.polyline(points, { color, weight, opacity: 1 }),
    ];
  },

  // The road path if we have one, otherwise straight lines between the stops
  points(item) {
    return item.path && item.path.length > 1 ? item.path : item.stops.map((s) => [s.lat, s.lng]);
  },

  _add(map, layers) {
    const group = L.featureGroup(layers).addTo(map);
    if (layers.length) map.fitBounds(group.getBounds(), this.FIT);
    return group;   // group.remove() clears it
  },

  // ---------- home page: every route as a coloured line ----------
  showNetwork(map, routes, stops) {
    map._stops = stops;
    const layers = [];
    routes.forEach((r) => {
      const [halo, ln] = this.line(this.points(r), r.color, 4);
      ln.bindTooltip(r.route, { sticky: true });
      ln.on("click", () => { window.location.href = "/routes/" + r.id + "/"; });
      layers.push(halo, ln);
    });
    stops.forEach((s) => {
      const dot = this.stopDot(s, "#1E2A33", 5);
      dot.on("click", () => { window.location.href = "/stops/" + s.id + "/"; });
      layers.push(dot);
    });
    return this._add(map, layers);
  },

  // ---------- one route ----------
  drawRoute(map, route) {
    map._stops = route.stops;
    const layers = [...this.line(this.points(route), route.color, 6)];
    route.stops.slice(1, -1).forEach((s, i) =>
      layers.push(this.label(this.stopDot(s, route.color), s.name, i % 2 ? "left" : "right")));
    const first = route.stops[0];
    const last = route.stops[route.stops.length - 1];
    layers.push(this.label(this.pin(first, "start", "A", first.name), first.name, "right", true));
    layers.push(this.label(this.pin(last, "end", "B", last.name), last.name, "right", true));
    const group = this._add(map, layers);
    this.declutter(map);
    return group;
  },

  // ---------- one stop ----------
  showStop(map, stop) {
    map._stops = [stop];
    const layer = this.pin(stop, "end", "&#9679;", stop.name).addTo(map);
    map.setView([stop.lat, stop.lng], 15);
    return layer;
  },

  // ---------- a journey: one coloured line per daladala ----------
  drawLegs(map, legs) {
    map._stops = legs.flatMap((leg) => leg.stops);
    const layers = [];
    let labelled = 0;   // alternate label sides so names overlap less
    legs.forEach((leg, index) => {
      const [halo, ln] = this.line(this.points(leg), leg.color, 6);
      ln.bindTooltip(leg.route, { sticky: true });
      layers.push(halo, ln);
      leg.stops.slice(1, -1).forEach((s) => {
        layers.push(this.label(this.stopDot(s, leg.color, 5), s.name, labelled++ % 2 ? "left" : "right"));
      });
      const first = leg.stops[0];
      layers.push(index === 0
        ? this.label(this.pin(first, "start", "A", MAP_TEXT.boardHere + ": " + first.name + " (" + leg.route + ")"), first.name, "right", true)
        : this.label(this.pin(first, "change", index, MAP_TEXT.changeHere + ": " + first.name + " (" + leg.route + ")"), first.name, "right", true));
    });
    const last = legs[legs.length - 1].stops.slice(-1)[0];
    layers.push(this.label(this.pin(last, "end", "B", MAP_TEXT.getOff + ": " + last.name), last.name, "right", true));
    const group = this._add(map, layers);
    this.declutter(map);
    return group;
  },
};
