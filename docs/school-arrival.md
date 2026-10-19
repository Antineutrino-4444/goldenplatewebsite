# School entrance animation

The camera starts over Jiamusi, turns toward the school's saved location, then
accelerates through a 1,400-ms eighth-power dive to zoom 18. The destination dot
renders in the map itself and the zoom center stays fixed.

The original fade is restored. The entire globe overlay fades away over 400 ms,
starting 300 ms before the camera arrives and ending 100 ms afterward. The fade
uses smootherstep opacity; the camera keeps its accepted speed and acceleration.
The portal underneath stays at its normal size and position. The circular mask,
four-panel break, impact pulse, canvas snapshots and portal transforms are removed.

The portal remains inert until the handoff finishes. Escape, the skip control,
reduced-motion preference, failed loading and cleanup retain their existing exits.

Validation on October 19, 2026: the focused animation tests and lint pass, and the
production frontend build passes. Checks cover camera acceleration, exact saved
coordinates, fade timing and bounds, loading safeguards and complete removal.
The HTTP preview uses a synthetic school/account with real map imagery and no
production records or email delivery.
