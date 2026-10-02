/* SAUD — Kuwait Fighter
   THEMES — each place's sky, ground, fog, lighting rig and clouds.

   These were the last colours in the game that were not data: they lived in
   the THEME table in index.html beside the code that draws each place. The
   data is here now (2026-10-02, asked as "add full color at data game"), so
   the Unreal build's export reads the same values the browser draws with;
   how each place is drawn -- its skyline, its arcades, its boats -- stays in
   index.html, which merges the two (data first, then drawing).

   One entry per `theme` named in stages.js:
     sky      three stops, top to horizon
     ground   two stops, far to near
     fog      the haze over the playfield
     rig      the light on the fighters: the key (direction x, y; colour;
              power), the fill, the rim, the toe and shoulder of the tone
              curve, the grade's three stops (position, colour), bloom,
              exposure, contrast, saturation and haze
     clouds   (some places) how many, where, how big, their colour and alpha,
              parallax and drift

   Loaded as a plain script before the game, so it works opened straight off
   disk with no build step and no server.
   ========================================================================== */
window.ASSET_THEMES = {
  souq: {
    sky:['#f2c98a','#e79a5c','#d97b4e'], ground:['#a5713f','#7c5230'], fog:'rgba(240,190,130,.28)',
    // Late afternoon. The sun is low and to the left, coming down the length of
    // the market; the open sky above fills the shadow side cold.
    rig:{ key:{x:-0.62,y:-0.72,col:'#ffd9a0',power:1.05}, fill:{col:'#7c9ad2',power:0.40},
          rim:{col:'#ffd28a',power:0.62}, toe:'rgba(26,16,10,.20)', shoulder:'rgba(255,246,226,.92)',
          grade:[[0,'rgba(96,150,235,0.094)'],[0.5,'rgba(180,170,170,0.014)'],[1,'rgba(255,146,52,0.108)']],
          bloom:0.22, exposure:1.05, contrast:1.10, saturate:1.14, haze:2.4 },
    clouds:{ n:5, y:70, spread:70, w:170, col:'#ffe6c0', alpha:0.30, par:0.03, speed:2.5 }
  },
  gym: {
    sky:['#2a3240','#1d2430','#161b25'], ground:['#4a3b2c','#332a20'], fog:'rgba(120,150,190,.10)',
    // Strip lights in the ceiling: hard, straight down, colourless. Indoors the
    // shadow side gets almost nothing back, so the rim does the separating.
    rig:{ key:{x:-0.18,y:-0.98,col:'#e8f0ff',power:1.12}, fill:{col:'#546070',power:0.24},
          rim:{col:'#bcd6ff',power:0.72}, toe:'rgba(13,16,23,.22)', shoulder:'rgba(240,246,255,.88)',
          grade:[[0,'rgba(120,175,235,0.101)'],[0.55,'rgba(150,155,170,0.014)'],[1,'rgba(255,168,88,0.079)']],
          bloom:0.16, exposure:1.02, contrast:1.14, saturate:1.06, haze:1.2 }
  },
  towers: {
    sky:['#0b1430','#152244','#26365e'], ground:['#2a3552','#1a2136'], fog:'rgba(90,140,220,.14)',
    // Night over the bay. Moonlight is weak; the towers behind throw the real
    // light, which is why the rim is the brightest thing on a fighter here.
    rig:{ key:{x:-0.44,y:-0.90,col:'#b8cfff',power:0.78}, fill:{col:'#3a5590',power:0.46},
          rim:{col:'#7fb6ff',power:0.86}, toe:'rgba(8,14,32,.26)', shoulder:'rgba(226,238,255,.86)',
          grade:[[0,'rgba(70,130,245,0.122)'],[0.5,'rgba(110,120,165,0.022)'],[1,'rgba(255,150,70,0.086)']],
          bloom:0.3, exposure:1.00, contrast:1.16, saturate:1.18, haze:2.0 }
  },
  failaka: {
    sky:['#ffb36b','#f07a5e','#8e4a6d'], ground:['#c3a173','#8e7350'], fog:'rgba(255,170,120,.24)',
    // The sun going down over the water, behind and to the right. Everything is
    // backlit, so this is the strongest rim in the game and the deepest colour.
    rig:{ key:{x:0.55,y:-0.74,col:'#ffb877',power:1.00}, fill:{col:'#9a5f8e',power:0.50},
          rim:{col:'#ff9a5c',power:0.95}, toe:'rgba(32,13,29,.22)', shoulder:'rgba(255,236,214,.90)',
          grade:[[0,'rgba(90,140,225,0.086)'],[0.45,'rgba(200,140,140,0.022)'],[1,'rgba(255,120,60,0.122)']],
          bloom:0.32, exposure:1.06, contrast:1.12, saturate:1.20, haze:2.8 },
    clouds:{ n:6, y:110, spread:80, w:190, col:'#ffd2a8', alpha:0.32, par:0.03, speed:2 }
  },
  desert: {
    sky:['#101a3a','#20264d','#3d3155'], ground:['#c2a274','#8b7047'], fog:'rgba(120,110,180,.16)',
    // Moon overhead, fire at ground level. Two lights of opposite temperature,
    // which is the oldest trick there is for making a night scene readable.
    rig:{ key:{x:-0.30,y:-0.94,col:'#c8d4ff',power:0.70}, fill:{col:'#4a4470',power:0.44},
          rim:{col:'#ff9d4a',power:0.80}, toe:'rgba(14,13,35,.26)', shoulder:'rgba(240,236,255,.84)',
          grade:[[0,'rgba(96,104,215,0.130)'],[0.5,'rgba(130,120,170,0.022)'],[1,'rgba(255,136,54,0.062)']],
          bloom:0.26, exposure:0.96, contrast:1.14, saturate:1.06, haze:2.2 }
  },
  fishmarket: {
    sky:['#8fbfd8','#c9d9dc','#e6d9bd'], ground:['#9aa6a4','#6e7877'], fog:'rgba(200,225,235,.20)',
    // Overcast morning. The whole sky is the light source: soft key, enormous
    // fill, barely any rim, and shadows that never reach black.
    rig:{ key:{x:-0.34,y:-0.94,col:'#f2f8fb',power:0.72}, fill:{col:'#b6cdd8',power:0.78},
          rim:{col:'#dceaf0',power:0.34}, toe:'rgba(48,58,66,.20)', shoulder:'rgba(250,253,255,.94)',
          grade:[[0,'rgba(140,195,230,0.094)'],[0.55,'rgba(180,190,190,0.022)'],[1,'rgba(230,180,120,0.079)']],
          bloom:0.14, exposure:1.03, contrast:1.11, saturate:1.02, haze:2.0 },
    clouds:{ n:7, y:60, spread:80, w:200, col:'#ffffff', alpha:0.34, par:0.04, speed:3 }
  },
  marina: {
    sky:['#120b26','#231245','#3a1c4e'], ground:['#3b3350','#241f33'], fog:'rgba(160,90,220,.14)',
    // Neon. Nothing here is white -- the signs behind the promenade are the
    // brightest source, so the silhouette edge burns magenta.
    rig:{ key:{x:-0.40,y:-0.90,col:'#9d7fd4',power:0.74}, fill:{col:'#4a2f6e',power:0.46},
          rim:{col:'#e46cff',power:0.92}, toe:'rgba(20,8,34,.26)', shoulder:'rgba(246,230,255,.86)',
          grade:[[0,'rgba(120,80,240,0.115)'],[0.5,'rgba(140,110,170,0.022)'],[1,'rgba(60,215,200,0.086)']],
          bloom:0.34, exposure:1.00, contrast:1.16, saturate:1.22, haze:2.2 }
  },
  highway: {
    sky:['#f0a15e','#c9683f','#6d3b4a'], ground:['#4a4a52','#2c2c33'], fog:'rgba(255,160,110,.20)',
    // Dusk on the dead road: an orange sky ahead, headlights behind, and grey
    // asphalt underneath giving almost nothing back.
    rig:{ key:{x:-0.58,y:-0.78,col:'#ffb070',power:0.96}, fill:{col:'#6b7a92',power:0.40},
          rim:{col:'#fff2d8',power:0.84}, toe:'rgba(20,17,26,.24)', shoulder:'rgba(255,244,226,.90)',
          grade:[[0,'rgba(88,142,235,0.101)'],[0.5,'rgba(170,150,140,0.022)'],[1,'rgba(255,140,64,0.115)']],
          bloom:0.28, exposure:1.03, contrast:1.13, saturate:1.14, haze:2.6 },
    clouds:{ n:5, y:80, spread:60, w:210, col:'#ffcda0', alpha:0.26, par:0.03, speed:2 }
  },
  arena: {
    sky:['#161020','#241633','#120c1c'], ground:['#5b4a63','#38293f'], fog:'rgba(180,108,224,.12)',
    // The title fight, lit like one: hard spots straight down, two more behind,
    // a crowd that returns almost nothing, and blacks allowed to go black.
    rig:{ key:{x:-0.10,y:-0.99,col:'#ffffff',power:1.08}, fill:{col:'#5b3a72',power:0.26},
          rim:{col:'#ffffff',power:1.00}, toe:'rgba(7,5,12,.26)', shoulder:'rgba(255,255,255,.94)',
          grade:[[0,'rgba(150,88,240,0.108)'],[0.5,'rgba(140,120,150,0.022)'],[1,'rgba(255,150,80,0.094)']],
          bloom:0.36, exposure:1.04, contrast:1.20, saturate:1.10, haze:1.4 }
  }
};
