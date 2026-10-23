"""15-Minuten-Mittelwert der Bezugsleistung nach Zählerzeit.

Grundlage ist der Zählerstand 1-0:1.8.0 (Wh) und die Zählerzeit 0-0:1.0.0 aus jedem Telegramm.
Viertelstundengrenzen werden in UTC bestimmt (Sommer-/Winterzeit spielt keine Rolle).
Der Zählerstand an einer Grenze wird zwischen dem letzten Telegramm davor und dem ersten
danach linear interpoliert.

Qualität einer Grenze:
  exakt        Telegramm genau auf der Grenze
  interpoliert Lücke zwischen den Telegrammen <= MAX_LUECKE_GENAU s
  naeherung    Lücke <= MAX_LUECKE_NAEHERUNG s
  (größer)     Grenze unbekannt -> Intervall ungültig

Ein Intervall ist gültig, wenn beide Grenzen bekannt sind, der Zählerstand nicht gefallen ist
und die Leistung die Plausibilitätsgrenze nicht überschreitet.
"""
from datetime import datetime, timezone

INTERVALL_S = 900
MAX_LUECKE_GENAU = 30
MAX_LUECKE_NAEHERUNG = 120
_RANG = {"exakt": 0, "interpoliert": 1, "naeherung": 2}


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


class Leistung15:
    def __init__(self, max_kw=17.3):
        self.max_kw = max_kw
        self._prev = None            # (t, e) letztes Telegramm
        self._start = None           # Beginn des laufenden Intervalls (epoch)
        self._e_start = None         # Zählerstand an der Startgrenze (Wh, ggf. interpoliert)
        self._q_start = None         # Qualität der Startgrenze
        self._grund_start = None     # warum der Start unbekannt ist

    def update(self, t, e, p_w):
        """Ein Telegramm verarbeiten.

        t   Zählerzeit als epoch-Sekunden (UTC)
        e   Zählerstand Bezug in Wh
        p_w aktuelle Bezugsleistung in W (für die Prognose)
        Rückgabe: (intervall | None, laufend) als dicts für MQTT
        """
        intervall = None
        grenze = (int(t) // INTERVALL_S) * INTERVALL_S

        if self._prev is None:
            # Erstes Telegramm nach dem Start: laufendes Intervall ist unvollständig
            if t == grenze:
                self._neuer_start(grenze, float(e), "exakt")
            else:
                self._start, self._e_start, self._q_start = grenze, None, None
                self._grund_start = "App-Start im Intervall"
        else:
            t0, e0 = self._prev
            if t <= t0:
                # Zeit läuft nicht vorwärts (doppeltes Telegramm / Uhr gestellt) -> ignorieren
                return None, self._laufend(t0, e0, p_w)
            if grenze > t0:
                # Mindestens eine Viertelstundengrenze überschritten
                luecke = t - t0
                if t == grenze:
                    e_g, q = float(e), "exakt"
                elif luecke <= MAX_LUECKE_NAEHERUNG:
                    e_g = e0 + (e - e0) * (grenze - t0) / luecke
                    q = "interpoliert" if luecke <= MAX_LUECKE_GENAU else "naeherung"
                else:
                    e_g, q = None, None

                if self._start is not None and grenze - self._start == INTERVALL_S:
                    intervall = self._abschluss(grenze, e_g, q, luecke)
                elif self._start is not None:
                    # Mehrere Grenzen übersprungen (Ausfall)
                    intervall = self._ungueltig(grenze - INTERVALL_S, grenze,
                                                f"Datenlücke {int(luecke)} s")
                if e_g is None:
                    self._start, self._e_start, self._q_start = grenze, None, None
                    self._grund_start = f"Datenlücke {int(luecke)} s an der Grenze"
                else:
                    self._neuer_start(grenze, e_g, q)

        self._prev = (t, e)
        return intervall, self._laufend(t, e, p_w)

    # ---- intern ----
    def _neuer_start(self, grenze, e_g, q):
        self._start, self._e_start, self._q_start, self._grund_start = grenze, e_g, q, None

    def _ungueltig(self, start, ende, grund):
        return {"start": _iso(start), "ende": _iso(ende), "energie_wh": None, "leistung_kw": None,
                "gueltig": False, "qualitaet": "ungueltig", "grund": grund}

    def _abschluss(self, ende, e_ende, q_ende, luecke):
        if self._e_start is None:
            return self._ungueltig(self._start, ende, self._grund_start or "Start unbekannt")
        if e_ende is None:
            return self._ungueltig(self._start, ende, f"Datenlücke {int(luecke)} s an der Grenze")
        energie = e_ende - self._e_start
        if energie < 0:
            return self._ungueltig(self._start, ende, "Zählerstand gefallen")
        kw = round(energie * 4 / 1000, 3)
        if kw > self.max_kw:
            return self._ungueltig(self._start, ende, f"{kw} kW über Plausibilitätsgrenze {self.max_kw} kW")
        q = max(self._q_start, q_ende, key=lambda x: _RANG[x])
        return {"start": _iso(self._start), "ende": _iso(ende), "energie_wh": round(energie, 1),
                "leistung_kw": kw, "gueltig": True, "qualitaet": q, "grund": None}

    def _laufend(self, t, e, p_w):
        sek = int(t - self._start) if self._start is not None else None
        d = {"start": _iso(self._start) if self._start is not None else None,
             "sekunden": sek, "restsekunden": INTERVALL_S - sek if sek is not None else None,
             "energie_wh": None, "mittel_kw": None, "prognose_kw": None,
             "gueltig": self._e_start is not None, "grund": self._grund_start}
        if self._e_start is None:
            return d
        energie = max(e - self._e_start, 0.0)
        rest = INTERVALL_S - sek
        prognose_wh = energie + max(p_w or 0, 0) * rest / 3600
        d.update({
            "energie_wh": round(energie, 1),
            "mittel_kw": round(energie * 3600 / sek / 1000, 3) if sek > 0 else None,
            "prognose_kw": round(prognose_wh * 4 / 1000, 3),
        })
        return d
