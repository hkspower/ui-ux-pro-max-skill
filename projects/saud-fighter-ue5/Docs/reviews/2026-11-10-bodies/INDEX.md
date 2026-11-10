# The men's bodies, reviewed -- 2026-11-10 (Riyadh)

Asked as "make full polish all character body shape fix", settled as: all six
Unreal men (Saud, the thug, the brawler, AL-SAQR, AL-WAHSH, ZAYOS), the whole
body; every shape fault found to be fixed in the builder and the men rebuilt.
The skeleton's joints stay where they are.

This folder is the review. Six reviewers each took one part (the trunk; the
arms and hands; the legs and feet; the men against each other; the surface;
the body as the game poses it), measured the built men in
`Tools/blender/rigs/*.blend` and looked at clay views of them, and reported at
most four findings each. One file per finding.

24 findings. Seven were then re-measured by a second reviewer whose job was to
refute them: 6 confirmed, 1 reproduced but judged not visible in play (B07).
**The other 17 were NOT checked by a second reviewer** -- that pass was cut
short -- so they are one reviewer's measurement each. Several of them are the
same fault met from different sides, which is its own kind of agreement:
B05 / B13 / B17 (the five canonical men's limbs lofted as straight cones),
B14 / B18 (no shoulder cap on the two big bosses), B02 / B16 (the big men
widened but not deepened), B09 / B15 (the seat and the side of the hip owned
by the thigh), B10 / B23 (a bent knee pinching).

`<scratch>` in these files is the review machine's scratch folder: the scripts
and clay pictures named there were not kept. The men measured are the ones
built before this review (the rigs as of commit 64c86db). Nothing here was
seen in an engine.

Whether each has been fixed since is recorded in the project's CLAUDE.md
("The men's bodies, reviewed"), not here.

| | severity | men | finding | review |
| --- | --- | --- | --- | --- |
| [B01](B01.md) | high | Zayos, Boss | The lat ends as a flap on the flank: a fin and a notch above the waist, bare on ZAYOS | confirmed by a second reviewer (on Zayos) |
| [B02](B02.md) | high | Zayos, Boss | The big men are widened but not deepened: ZAYOS's trunk is a board, twice as wide as it is deep | confirmed by a second reviewer (on Zayos) |
| [B03](B03.md) | medium | Thug, Zayos, Boss | The hip line: the trunk's width changes in 4 cm at the waistband -- a hip shelf on the thug, the band overhanging the hips on ZAYOS | confirmed by a second reviewer (on Thug, Zayos) |
| [B04](B04.md) | medium | Zayos | ZAYOS's trousers stand off his bare waist as an open rim | confirmed by a second reviewer (on Zayos) |
| [B05](B05.md) | high | Thug, Brawler, Saqr, Boss, Zayos | Five men's arms are still the old straight-lofted tube: ridged cones, the biceps all in front, a club swelling below a deltoid that did not grow | confirmed by a second reviewer (on Thug, Brawler, Saqr, Boss, Zayos) |
| [B06](B06.md) | high | Zayos | ZAYOS's gloves: his fingers stand through them, the closed fist crumples them, and they are narrower than his forearm | confirmed by a second reviewer (on Zayos) |
| [B07](B07.md) | medium | Saud, Thug, Brawler, Saqr, Boss, Zayos | The point of the elbow collapses to half in every guard: the bent arm is thinnest exactly where it bends | reproduced, judged not visible in play |
| [B08](B08.md) | medium | Saud, Thug, Brawler, Saqr, Boss, Zayos | The closed fist: fingertips and thumb end inside the palm, the fingers slide a finger-width toward the little finger, and the thumb is built behind the hand | measured by its finder; NOT checked by a second reviewer |
| [B09](B09.md) | high | Saud, Thug, Brawler, Saqr, Boss, Zayos | The seat swings with the thigh: when a leg is raised (round kick, knee strike) the buttock is dragged 16-28 cm under the pelvis, balloons into a bag and folds through itself | measured by its finder; NOT checked by a second reviewer |
| [B10](B10.md) | high | Saud, Thug, Brawler, Saqr, Boss, Zayos | A bent knee pinches like a hose: in the knee strike the kneecap falls to 50-58 % of its distance from the joint and the leg is 7.6 cm thick through the hinge where it is 13.3 at rest | measured by its finder; NOT checked by a second reviewer |
| [B11](B11.md) | medium | Saud, Thug, Brawler, Saqr, Boss, Zayos | The trainers are a wedge on a rectangular plank: the sole is a 9.8 x 32 cm box with square corners, the upper tapers to a 4.5 cm point on top of it and has no instep | measured by its finder; NOT checked by a second reviewer |
| [B12](B12.md) | medium | Thug, Boss, Zayos | The size field thickens the knee like muscle and leaves the top of the thigh alone: AL-WAHSH's and ZAYOS's legs are columns (ZAYOS's thigh is fatter at its middle than at the groin), the thug's a cone down to a 35 cm trousered knee | measured by its finder; NOT checked by a second reviewer |
| [B13](B13.md) | high | Thug, Brawler, Saqr, Boss, Zayos | The five men other than Saud have lathe-turned arms: a hard ring round the forearm and another round the upper arm | measured by its finder; NOT checked by a second reviewer |
| [B14](B14.md) | high | Boss, Zayos | AL-WAHSH and ZAYOS have no shoulder cap: the size field thickens the arm below the shoulder and leaves the deltoid at Saud's size | measured by its finder; NOT checked by a second reviewer |
| [B15](B15.md) | high | Saud, Thug, Brawler, Saqr, Boss, Zayos | In the guard the top of each trouser leg stands out of the seat as a slab with a ledge: the thigh owns the whole side of the hip up to the waistband | measured by its finder; NOT checked by a second reviewer |
| [B16](B16.md) | medium | Zayos, Boss | ZAYOS (and less so AL-WAHSH) is widened but not deepened: a plank of a trunk over legs deeper than his chest | measured by its finder; NOT checked by a second reviewer |
| [B17](B17.md) | high | Thug, Brawler, Saqr, Boss, Zayos | The limbs of the five canonical men are chains of straight cones: a hard ring at every loft row (Saud's were smoothed, theirs were not) | measured by its finder; NOT checked by a second reviewer |
| [B18](B18.md) | high | Thug, Boss, Zayos | No deltoid on the canonical men: the arm is a tube whose cut end shows as a rim at the shoulder, and on the two big bosses it is thinner at the shoulder than at the biceps | measured by its finder; NOT checked by a second reviewer |
| [B19](B19.md) | medium | Thug, Boss | The singlet takes a strip of the upper arm: a loose scrap of cloth under each arm and holes through the arm's skin beside it | measured by its finder; NOT checked by a second reviewer |
| [B20](B20.md) | medium | Thug, Brawler, Saqr, Boss, Zayos | The track trousers fold over and through themselves at the front hips and along the inseam (the jogger was cured of this, the track cut was not) | measured by its finder; NOT checked by a second reviewer |
| [B21](B21.md) | high | Saud, Thug, Brawler, Saqr, Boss, Zayos | The wrist is wrung to a thread when the fist turns over (candy-wrapper): every jab, cross and hook | measured by its finder; NOT checked by a second reviewer |
| [B22](B22.md) | high | Saud, Thug, Brawler, Saqr, Boss, Zayos | The neck shears into a sliding flap and fins when the head turns or tilts: the skull's whole turn is taken in 3 cm at the base of the neck | measured by its finder; NOT checked by a second reviewer |
| [B23](B23.md) | medium | Saud, Thug, Brawler, Saqr, Boss, Zayos | The outside of every bent joint caves in by the cosine of half the bend: no elbow point in the guard, a bent-pipe knee, a flattened buttock on the kicking leg | measured by its finder; NOT checked by a second reviewer |
| [B24](B24.md) | medium | Saud, Thug, Brawler, Saqr, Boss, Zayos | The wrist is folded back 104-155 degrees in every kick and knee (and on the floor): the pose tables aim the forearm and leave the hand on the guard's aim | measured by its finder; NOT checked by a second reviewer |
