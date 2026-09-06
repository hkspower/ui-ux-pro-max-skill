/* AHMED — Kuwait Fighter
   ENEMIES — the ten archetypes.

   `col` is the palette, `look` the kit. Silhouette carries the read in a
   crowded wave, so build, headwear and garment matter more than colour:
   see the roster table in README.md.

   Loaded as a plain script before the game, so it works opened straight off
   disk with no build step and no server. Edit the numbers here; the game
   reads them and never keeps its own copy.
   ========================================================================== */
window.ASSET_ENEMIES = {
  thug:    {hp:46,  pow:.80, spd:120, reach:54, rate:1.55, xp:14, sc:1.00,
            moves:['jab','cross'], name:'Souq Thug', ar:'بلطجي',
            col:{skin:'#b8794c', top:'#8a9099', bottom:'#2f3a4d', band:'#8d99ab'},
            look:{ build:0.90, tee:true, pants:true, hands:'bare', hair:'#26221c' }},
  brawler: {hp:68,  pow:1.00, spd:132, reach:58, rate:1.25, xp:21, sc:1.05,
            moves:['jab','cross','hook'], name:'Brawler', ar:'مشاكس',
            col:{skin:'#a86c42', top:'#8c4a34', bottom:'#3a2f28', band:'#c8102e'},
            look:{ build:1.12, tee:true, pants:true, hands:'bare', beard:'rgba(34,24,16,.85)', hair:'#2a1d13' }},
  kicker:  {hp:60,  pow:1.15, spd:162, reach:74, rate:1.10, xp:26, sc:1.02,
            moves:['kick','jab','kick','cross'], name:'Kickboxer', ar:'ملاكم',
            col:{skin:'#c08a58', top:'#1f8a63', bottom:'#232a36', band:'#e0b34a'},
            look:{ build:0.98, tee:true, pants:true, hoodie:true, stripe:true, hands:'wraps', hair:'#1d1a15' }},
  grappler:{hp:110, pow:1.35, spd:98,  reach:46, rate:1.75, xp:34, sc:1.18,
            moves:['knee','hook','knee'], name:'Grappler', ar:'مصارع',
            col:{skin:'#9c6236', top:'#6b7280', bottom:'#26292f', band:'#7d8794'},
            look:{ build:1.30, tee:true, pants:true, hands:'bare', bald:true, scar:true }},
  champ:   {hp:160, pow:1.35, spd:152, reach:68, rate:0.95, xp:52, sc:1.10,
            moves:['jab','cross','kick','hook','knee'], name:'Contender', ar:'منافس',
            col:{skin:'#b5794a', top:'#6b3bb0', bottom:'#22243a', band:'#e0b34a'},
            look:{ build:1.14, tee:true, pants:true, jacket:true, hands:'wraps', hair:'#1a1410', beard:'rgba(26,18,12,.7)' }},
  runner:  {hp:42,  pow:0.85, spd:210, reach:56, rate:0.85, xp:22, sc:0.94,
            moves:['jab','jab','cross'], name:'Runner', ar:'خطّاف', hitRun:true,
            col:{skin:'#c2905f', top:'#e07b2c', bottom:'#2c3550', band:'#ffd166'},
            look:{ build:0.88, tee:true, pants:true, hoodie:true, hands:'bare', cap:'#d4762b', hair:'#231a12' }},
  bouncer: {hp:150, pow:1.30, spd:104, reach:52, rate:1.90, xp:40, sc:1.24,
            moves:['hook','knee','hook'], name:'Bouncer', ar:'حارس', wall:true,
            col:{skin:'#8a5730', top:'#191d24', bottom:'#12151a', band:'#5aa9e6'},
            look:{ build:1.32, tee:true, pants:true, hands:'bare', bald:true, shades:true }},
  capo:    {hp:118, pow:1.20, spd:168, reach:64, rate:0.78, xp:44, sc:1.06,
            moves:['jab','cross','hook','jab','kick'], name:'Enforcer', ar:'مُنفّذ',
            col:{skin:'#a86c42', top:'#1f6a80', bottom:'#1a2230', band:'#8fd3ff'},
            look:{ build:1.08, tee:true, pants:true, jacket:true, hands:'bare', hair:'#141922', shades:true }},
  boss:    {hp:430, pow:1.45, spd:146, reach:72, rate:0.88, xp:220, sc:1.26,
            moves:['jab','cross','hook','kick','knee'], name:'AL-WAHSH', ar:'الوحش',
            col:{skin:'#8f5a30', top:'#1b1f26', bottom:'#101318', band:'#c8102e'},
            look:{ build:1.36, tee:true, pants:true, hands:'wraps', bald:true, beard:'rgba(20,14,10,.92)', scar:true }},
  saqr:    {hp:290, pow:1.30, spd:186, reach:76, rate:0.80, xp:150, sc:1.14,
            moves:['kick','jab','kick','cross','knee'], name:'AL-SAQR', ar:'الصقر',
            col:{skin:'#c08a58', top:'#2c4a8a', bottom:'#20242e', band:'#e8e2d4'},
            look:{ build:1.12, tee:true, pants:true, hoodie:true, stripe:true, hands:'wraps', hair:'#1b1712' }}
};
