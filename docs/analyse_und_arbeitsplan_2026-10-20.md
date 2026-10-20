# Qualitätsanalyse und Arbeitsplan

Stand: 20.10.2026. Diese Arbeitsgrundlage unterscheidet nachgewiesene Codefehler,
methodische Fragen und fehlende Messungen. Sie ergänzt die
[RC2-Auslieferungsakte](rc2_release_2026-10-20.md) und die
[Upstream-Pakete](rc2_upstream_2026-10-20.md). Die Wetterstationsanbindung ist
ein Vorschlag und gehört nicht zum Funktionsumfang von RC2.

## Bezug und Gesamturteil

Untersuchter Upstream-main: `76d305ebfced57fe254a6f1553404337d8e2fff1`;
Upstream-develop: `c5fff9d479605c38b2d72031cbf82b283ef4814d`.
Vollständige veröffentlichte Fork-Auslieferungsbasis:
`569074a42399a2e5e954b01da8ce34240fa1341e`.
RC2-Implementierung: `43e489c1115e194cdf46fb7b36a8e942bceaad98`;
anschließende Testkorrektur und erste Dokumentationsfassung:
`b0a574dc33e94ebdd2ef579fe6fe759e119da03e`.
Der endgültige Dokumentations-/Review-/Auslieferungspin wird nach dem letzten
Source-Freeze in den ignorierten dynamischen Belegen erfasst.

Helios hat einen zugänglichen, weitgehend HA-unabhängigen Rechenkern, explizite
physikalische Annahmen und viele schnelle Tests. Sinnvoll sind die vorsichtige
Behandlung begrenzter Erzeugung, fehlende Bänder statt erfundener Zahlen und die
Möglichkeit, Modellvarianten offline zu prüfen. Das erleichtert Weiterentwicklung.

Die Prognosegüte ist damit noch nicht allgemein bewiesen. Die öffentliche
[Benchmark-Seite](https://helios-ha.org/benchmark/) nennt zum Abrufzeitpunkt einen
Teilnehmer, weniger als eine volle Saison und den Neustart der Messrunde am
08.09.2026. Das ist eine begrenzte Evidenzbasis; es existieren durchaus Messungen.
Ein passender Leistungswert im README belegt keine Güte über Wetterlagen,
Jahreszeiten und Horizonte. Kommentare zur Flottenkalibrierung von Verlustfaktor
und IAM sind dokumentierte Autorenentscheidungen; die Rohdatenrechnung wurde
hier nicht unabhängig wiederholt.

## Prüfung der vorgelegten Fremdanalyse

| Thema | Eigener Befund | Konsequenz |
| --- | --- | --- |
| Vereinheitlichte Energy-Netzzähler | Bestätigter Kompatibilitätsfehler: ausschließlich alte Flow-Listen zu lesen verliert Import/Export im neuen Format. | RC2 liest beide Formen ohne doppelte Zählung; fehlende Verbrauchsevidenz erzeugt einen Repair. Upstream #86 wird anerkannt. |
| Residual-Map bei Analog-Confidence 1 | Der explizite Residual-Anteil im Blend wird null. Derselbe Standortfehler kann aber bereits im Analog-Anteil stecken. | Vor einer Architekturänderung beide Lernwege gemeinsam untersuchen. |
| Vorgeschlagener Fix `pv_w * ratio` | Als pauschaler Fix ungeeignet: die Analog-Ratio ist bereits gemessene Leistung geteilt durch rohe Physik. | Kann denselben Standortverlust doppelt anwenden; in RC2 nicht übernommen. |
| Basis von Analog-Band und Deckel | Rohe Physik ist die passende Rückskalierung einer actual/raw-Ratio. Die statistische Abstimmung von Blend, Band und Deckel ist eine weitere Frage. | Kalibrierung messen; unterschiedliche Zwischenwerte allein beweisen keinen Skalierungsfehler. |
| Auswahl der besten 60 Analoge | Eine übliche Nachbarschaftsauswahl, kein Beweis für systematisch zu schmale Bänder. Gleich gute Kandidaten können allerdings von ihrer Eingabereihenfolge abhängen. | Gleichstände, effektive Stichprobe und Banddeckung gezielt prüfen. |
| Feste Refresh-Phase und kurze Retries | Strukturelles Last-/Verfügbarkeitsproblem bestätigt; der bestehende Beitrag #92 adressiert es. | Vorhandene Arbeit erhalten; RC2 ergänzt Wiederverwendung der Wetterhistorie. |
| 60 Tage Wetter bei jedem Refresh | Unnötige Wiederholung bestätigt. Gemeldete Provider-Latenzen sind standort-/modellabhängig. | RC2 trennt kurze Aktualisierung und historischen Backfill. |
| Klarwettergewicht in der Residual-Map | Gewichtung sichtbar; dass sie die falschen Samples abwertet, ist nicht kontrolliert nachgewiesen. | Ablation statt sofortigem Entfernen; sonst können Wolkenfehler als Dachverlust gelernt werden. |
| Reliability als Genauigkeit missverstanden | Berechtigtes Verständlichkeitsproblem: Reife, Skill und Vorhersagbarkeit sind verschiedene Bestandteile. | Bestandteile und fehlende Evidenz erklären; keine Trefferwahrscheinlichkeit versprechen. |
| Einzelne schlechte Prognosen/Issues | Hinweise, kein hinreichender Nachweis einer bestimmten Ursache. | Mit Originaldaten Wetter-, Physik-, Lern- und Anzeigeanteile auseinanderhalten. |

Gegenprobe zur vorgeschlagenen Lernkorrektur: rohe Physik 5000 W,
standortkorrigierte Physik 3000 W, gelernte actual/raw-Ratio 0,6.
Der Analog-Anteil liefert bereits 3000 W; Multiplikation mit der korrigierten
Physik ergäbe 1800 W. Ein kumulatives Modell wäre möglich, bräuchte aber andere
Trainingsziele, etwa actual/residual-corrected, und konsistente Änderungen von
Training, Vorhersage und Replay.

Confidence hängt von nahen Stunden-Samples ab, nicht unmittelbar von einer festen
Zahl gelernter Tage. Sie wird je Vorhersagepunkt berechnet; die Analog-Ratio ist
keineswegs über den Tag konstant. Die Distanzschwelle allein beschreibt auch keine
harte Auswahlbox: Rangfolge, Gewichtung und K-Auswahl bestimmen die Analoge.
Die Aussage, die Map-Abschaltung erkläre ein bestimmtes Issue vollständig, ist
deshalb nicht belegt.

P10/P90 aus Helios und einem ML-Verfahren lassen sich empirisch auf Kalibrierung
vergleichen, wenn Ausgabezeit, Horizont, Zielintervall, AC/DC-Bezug, Einheit und
Wahrheitszähler übereinstimmen. Die Modellklasse entscheidet diese Frage nicht.
Ein breiteres Band ist nicht automatisch ehrlicher. Die Summe stündlicher P10
ist im Allgemeinen kein Tages-P10.

## Zusätzlich nachgewiesene und in RC2 behobene Fehler

Analog-Verfeinerung konnte die zuvor begrenzte Wechselrichterleistung wieder
überschreiten. Eine Regression reproduziert 6300 W nach einer physikalisch auf
4500 W begrenzten Vorhersage. RC2 begrenzt den fertigen Punkt und vorhandene
Bänder erneut an konfigurierten Hardwaregrenzen, einschließlich produzierender
Teilanlagen. Rohe Referenz und fehlende Bänder bleiben erhalten. Live-, vergangene
Kartenpunkte und rekonstruierte Archivpunkte nutzen denselben Abschluss.

Das Replay war mit dem aktuellen Vertrag nicht ausführbar: ein erforderlicher
Wechselrichterparameter fehlte, der Export verwendete alte Statistik-IDs.
Gemessene Tageslichtstunden mit null Produktion blieben aus der Bewertung.
RC2 repariert Eingaben/Export und verlangt passende vollständige Stundenbelege.
Installation, Geometrie, Zeitzone und Zähler kommen aus privater Konfiguration.
Trainiert wird nur mit dem zum jeweiligen 06:00-Ursprung verfügbaren
Erzeugungswissen. Echte Nullproduktion zählt mit, fehlende Produktion nicht.

Replay mit rückblickend archiviertem Wetter isoliert Lern-/Modellvarianten,
rekonstruiert aber keine ursprünglich ausgegebene Wettervorhersage.
Zurückgerechnete Helios-Archivwerte sind ebenfalls keine unveränderlich
gespeicherten damaligen Prognosen. RC2 behauptet keine stündliche
Quantilkalibrierung aus einem Minimum/Maximum momentaner Bänder.

Die neue Wetterhistorie speichert ausschließlich vergangene Stunden, prüft
Identität/Integrität und verwendet zunächst den vollständigen Bezug, danach einen
kurzen Bezug mit begrenztem Backfill. Alte Zukunftsprognosen werden nicht durch
Zeitablauf zu Beobachtungen. Originale Abrufbelege bleiben ihren Stunden zugeordnet.
Ein Neustart braucht weiterhin frische brauchbare Wetterdaten; der erste volle
Bezug kann langsam bleiben. Details: [WEATHER_API.md](../WEATHER_API.md).

Belegte RC2-Prüfungen: 334 reine Python- und 144 HA-Tests, Lint/Format/Typprüfung
und 36 unabhängige Release-Prüffälle. Die HA-Suite nutzt einen gepinnten älteren
Harness; zusätzliche Imports gegen Core 2026.10.2 sind kein vollständiger aktueller
Core-Test. Der vorherige fehlgeschlagene HA-Lauf und seine Fixture-Korrektur sind
in der Auslieferungsakte erfasst. Tests und AI-Reviews ersetzen keine saisonale
Genauigkeitsmessung. Die finalen Delivery-Gates gelten erst mit frischen Belegen.

## Lokale Wetterstation

**Globalstrahlung ist der interessanteste zusätzliche Stationswert.** Zu prüfen
sind kurzfristige Fortschreibung, Wetterfehlerdiagnose und die Trennung von
Wetterabweichung und PV-Modellabweichung. Eine aktuelle Messung beobachtet keine
künftigen Wolken; ein einzelner Sensor liefert keine heranziehende Wolkenkarte.
Messgestützte Persistenz ist ein geeigneter Vergleichsmaßstab.
[NREL-Forschung zu physikalischer Smart Persistence](https://www.nrel.gov/docs/fy22osti/81421.pdf)
berichtet zugleich zunehmende Fehler mit wachsendem Horizont. Das beweist keinen
Nutzen für diese Integration oder den eigenen Standort.

Die lokale Bestandsprüfung fand Strahlung in W/m² sowie Temperatur, Wind,
Feuchte, Luftdruck und Niederschlag. Geräte-/Entity-Zuordnungen und konkrete
Messwerte bleiben in privaten Betriebsbelegen außerhalb von Git und AI-Review.
Der Nachtabruf verifiziert Datentypen, weder Tageskalibrierung noch Sensorgüte oder
eine unabhängige Gerätezeit. Bei gleichem Messwert können HA-Zeitstempel alt bleiben;
ihre Eignung als Frischesignal muss am tatsächlichen Geräte-/Integrationsverhalten
geprüft werden.

| Eingang | Möglicher Nutzen | Vorbedingung / Grenze |
| --- | --- | --- |
| Globalstrahlung/GHI | Kurzfristiges Wolkenniveau, Wetterfehlerdiagnose, Modellvergleich | Sensorfläche, Abschattung, Kalibrierung und Zeitbezug prüfen; W/m² sind keine PV-Watt. |
| Außentemperatur | Lokaler Eingang der Temperatur-/Leistungsrechnung | Lufttemperatur ist keine Modultemperatur; Messort und Sonnenschutz prüfen. |
| Windgeschwindigkeit | Ergänzung eines passenden thermischen Modells | Einheiten umrechnen; Exposition gegen Module prüfen; Böe ist kein Stundenmittel. |
| Echte Modul-/Rückseitentemperatur, falls vorhanden | Näherer Anhaltspunkt für aktuellen thermischen Leistungsverlust | Position und Übertragbarkeit zwischen Teilanlagen; nicht automatisch Stationsbestandteil. |
| Regen, Schnee, Sensorstatus | Qualitätsmerkmale, mögliche Verschmutzung/Schneebedeckung | Regen beweist keine Reinigung; Regensensor misst keine Modul-Schneedecke. |
| Feuchte, Taupunkt, Druck | Mögliche spätere Zusatzmerkmale/Diagnose | Nutzen separat nachweisen; zunächst geringe Priorität. |
| UV, Lux | Ergänzende Plausibilität | Kein universeller Lux-/UV-zu-GHI-Faktor; kein gleichwertiger Strahlungseingang. |
| Windrichtung | Thermische/Standortdiagnose | Bodenwind allein ist kein verlässlicher Wolkenbewegungsvektor. |

GHI bezeichnet Einstrahlung auf eine horizontale Fläche. Ein Stationssensor ist
nicht automatisch ein kalibriertes, horizontal montiertes Pyranometer.
Gerätemodell, Aufstellung und Tagesvergleich klären die verwendbare Größe.
Geneigte PV-Flächen sehen andere Einstrahlung. Ein GHI-Wert bestimmt Direkt- und
Diffusanteil nicht eindeutig; eine Zerlegung muss als Modellschätzung erkennbar
und konsistent sein. Gemessene GHI zusammen mit unveränderten Provider-Komponenten
kann widersprüchliche Strahlung erzeugen. Open-Meteo erläutert
[Komponenten und Zeitbezüge](https://open-meteo.com/en/docs/satellite-radiation-api):
Momentanwerte und rückblickende Intervallmittel sind unterschiedliche Größen.
Vergleiche müssen dieselben Zeitfenster verwenden.

Eine verschattete Station kann ihren eigenen Horizont abbilden, während andere
Dachflächen noch Sonne sehen. Eine entfernte Station ist ein räumlicher Hinweis,
keine gleichwertige lokale Wahrheit. Deshalb weder eine feste Korrekturratio über
sieben Tage fortschreiben noch unkontrolliert mit schon gelernten Dach- und
Wetterkorrekturen multiplizieren.

### Architekturvorschlag

1. Optionaler Beobachtungseingang mit Herkunft, Einheit, Gerätezeit soweit vorhanden,
   HA-Empfangszeit, Qualitätsstatus und Abdeckungsdauer. Ohne gültige Beobachtung
   bleibt der Providerpfad maßgeblich.
2. Beobachtung, ursprüngliche Wetterprognose und ausgegebene PV-Prognose getrennt
   speichern. Revisionen behalten Ausgabe-/Bekanntzeit, Zielintervall, Modellversion
   und Hash. Fehlend bleibt fehlend, echte Null bleibt null. Nacht, Ausfall,
   unveränderter Wert und Abschattung sind verschiedene Zustände.
3. Offline robuste Clear-Sky-Persistenz und eine mit dem Horizont abklingende
   Verbindung zur Providerprognose prüfen. Gewichte/Horizont aus zurückgehaltenen
   Tagen bestimmen. Bei tiefem Sonnenstand keine instabile Division; bei
   ungültigem Sensor definierter Provider-Fallback.
4. Nach erfolgreicher Offline-Prüfung einen standardmäßig deaktivierten
   Shadow-Modus erwägen. Eingangsherkunft und Ausgabe bleiben vom normalen
   Forecast unterscheidbar. Hardwaregrenzen gelten nach jeder Kombination.
5. Residual-/Analog-Training auf gemessene Einstrahlung ist ein eigenes Modellpaket
   mit versionierter Trainingsbasis und erneutem Replay. Unterschiedliche
   Trainingsnenner nicht still vermischen.

## Fortsetzbare Arbeitspakete

Diese Reihenfolge bevorzugt verlässliche Vergleichsdaten vor Lernänderungen.
Die Stationsanbindung wird durch diese Dokumentation nicht aktiviert.

| Paket | Inhalt / Abhängigkeit | Abnahme |
| --- | --- | --- |
| A: RC2 ausliefern | Autorisierte Korrekturen, frische Full-/Meta-Reviews, Fork-Push, getrennte Upstream-Entwürfe, unveränderlicher RC2 und gesicherter HA-Update | Exakter Commit/Asset-Hash, grüne Checks, Backup mit Recorder, Code-/Versions-/Eintrags-/Daten-Readback; Neustart belegt keine Genauigkeit. |
| B: Vergleichsdaten | Originale Wetter-/PV-Prognosen mit unveränderlichen Zeitbezügen sichern; bestehende Speicher zuerst inventarisieren | Keine Zukunftsdaten im Training; begrenzte/lückenhafte Erzeugung markiert; gleiche Zähler, Intervalle und Einheiten. |
| C: Stationsdaten prüfen | Bestands-/Historienanalyse für Strahlung, Temperatur und Wind; Gerätespezifikation, Montage, Einheiten, Frequenz/Lücken | Tageslichtvergleich über mehrere Wetterlagen; Frischesignal prüfen; keine stillen Null-/Interpolationswerte. Private Zuordnungen bleiben privat. |
| D: Nowcast offline | B+C; Provider, Persistenz und Clear-Sky-Persistenz vergleichen, danach Temperatur/Wind einzeln ergänzen | Zeitlich getrennte Trainings-/Prüftage; Fehler je 5/15/30/60/120 Minuten soweit Datenauflösung trägt; Tagesvorhersage separat. Ausfall-Fallback prüfen. |
| E: Lernen und Bänder | Replay für Residual-only, Analog-only und heutigen Blend; K-Gleichstände, effektive Sample-/Tageszahl, Kernel und Klarwettergewicht | Walk-forward ohne Optimierung auf Prüftagen; Bias, Punktfehler und P10/P90-Deckung/Quantilverlust auf passender Zielgröße; Abregelung/Horizontlagen getrennt. |
| F: Horizontprofil | Reproduzierte Standort-/Physikfehler aus B/E; azimutabhängige direkte Abschattung | Direktstrahl dämpfen, Diffuslicht nicht pauschal löschen; identische Physik in Training/Live/Replay. Winkelauflösung nicht universell in Minuten umrechnen. |
| G: Optionale Stationsanbindung | Erst nach C/D mit eigenem Funktionsscope; reiner Kern, HA-Adapter, versionierte Herkunft | Fehler-/Einheiten-/Zeit-/Fallbacktests, Shadow-Vergleich, Gemini-Review und gesonderte Freigabe für diese neue Funktion. |

B bis G jeweils mit enger Datei-Allowlist, eingefrorener Basis,
Verhaltenserwartungen und eigenen Abnahmekriterien beginnen. Implementierungen
wie gewünscht an Subagents mit hohem Reasoning-Effort delegieren. Fehlende
Gerätespezifikationen oder Originalprognosen als Evidenzgrenze ausweisen;
archiviertes Wetter nicht als damals bekannte Prognose darstellen.

Nach RC2 sind C und die Inventur für B sinnvoll: Sie klären mit vorhandenen Daten,
ob die Strahlungsmessung eine belastbare Grundlage für D liefert. Erst danach
lässt sich eine konkrete Verbesserung beziffern. RC2 ändert keine ESS-Regelung,
Benchmark-Teilnahme oder Quellenwahl anderer Prognoseverfahren.
