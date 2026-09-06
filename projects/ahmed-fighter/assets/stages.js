/* AHMED — Kuwait Fighter
   STAGES — the nine places, plus survival.

   `len` is how far the area runs in world px; `waves` are the ambushes and
   `at` is the x that triggers each one. A wave with `at:-1` spawns the moment
   the one before it clears, which is how survival works. `gates` are the
   sealed routes inside an area — always against the back wall, so an area is
   completable without them. `theme` picks the backdrop and the lighting rig
   from THEME in index.html; `tier` picks the difficulty band.

   How the areas CONNECT is world.js, not this file. This is what is inside
   each one.

   Loaded as a plain script before the game, so it works opened straight off
   disk with no build step and no server. Edit the numbers here; the game
   reads them and never keeps its own copy.
   ========================================================================== */
window.ASSET_STAGES = [
  { name:'SOUQ MUBARAKIYA', ar:'سوق المباركية', theme:'souq', len:2900, tier:0,
    hint:'Trouble in the old market.',
    gates:[{at:1150, type:'wall', reward:{xp:450}}],
    story:['A crew has been leaning on the traders in the old souq for months.',
           'Ahmed grew up in these alleys. Tonight he stops being a bystander.'],
    storyAr:'بدأت الحكاية في سوق المباركية',
    waves:[ {at:560,  e:[['thug',2]]},
            {at:1520, e:[['thug',2],['brawler',1]]},
            {at:2450, e:[['brawler',2],['thug',1]]} ] },

  { name:'SALMIYA GYM', ar:'نادي السالمية', theme:'gym', len:2900, tier:0,
    hint:'Spar your way through the club.',
    gates:[{at:2000, type:'stash', reward:{ability:'vault'}}],
    story:['Word travels. The Salmiya club wants to see what the souq kid can do.',
           'Six rounds, no headgear, and nobody is holding back.'],
    storyAr:'الاختبار الأول في نادي السالمية',
    waves:[ {at:540,  e:[['brawler',2]]},
            {at:1480, e:[['kicker',2],['thug',1]]},
            {at:2420, e:[['kicker',2],['brawler',2]]} ] },

  { name:'SHARQ FISH MARKET', ar:'سوق شرق للسمك', theme:'fishmarket', len:3000, tier:1,
    hint:'Dawn on the harbour. They came early.',
    gates:[{at:1050, type:'ledge', reward:{ability:'dashleap'}}],
    story:['The crew moved their business to the harbour before sunrise.',
           'Wet stone, cold air, and runners who will not stand still.'],
    storyAr:'الفجر على الميناء',
    waves:[ {at:560,  e:[['runner',2],['thug',1]]},
            {at:1520, e:[['runner',2],['brawler',2]]},
            {at:2500, e:[['bouncer',1],['runner',2]]} ] },

  { name:'KUWAIT TOWERS', ar:'أبراج الكويت', theme:'towers', len:3100, tier:1,
    hint:'Night raid on the waterfront.',
    gates:[{at:1150, type:'wall', reward:{xp:500}}],
    story:['They want the waterfront cleared before the season opens.',
           'Ahmed gets there first.'],
    storyAr:'ليلة على الواجهة البحرية',
    waves:[ {at:600,  e:[['kicker',2],['thug',1]]},
            {at:1600, e:[['brawler',2],['kicker',1]]},
            {at:2600, e:[['grappler',1],['kicker',2]]} ] },

  { name:'MARINA CRESCENT', ar:'مارينا كريسنت', theme:'marina', len:2600, tier:2,
    hint:'AL-SAQR runs this strip.',
    gates:[{at:950, type:'gap', reward:{ability:'powerkick'}}],
    story:['The neon strip belongs to AL-SAQR — the Falcon. All legs, no patience.',
           'Beat him and the crew loses its enforcer.'],
    storyAr:'الصقر يحرس المارينا',
    boss:true,
    waves:[ {at:560,  e:[['capo',1],['runner',2]]},
            {at:1400, e:[['bouncer',1],['capo',1]]},
            {at:2100, e:[['saqr',1]]} ] },

  { name:'FAILAKA ISLAND', ar:'جزيرة فيلكا', theme:'failaka', len:3100, tier:2,
    hint:'Grapplers hold the ruins.',
    gates:[{at:2150, type:'shutter', reward:{xp:600}}],
    story:['They regrouped on the island, among the old stone.',
           'Nowhere to run out here — which cuts both ways.'],
    storyAr:'بين آثار فيلكا',
    waves:[ {at:600,  e:[['grappler',1],['brawler',1]]},
            {at:1600, e:[['grappler',2],['kicker',1]]},
            {at:2600, e:[['grappler',2],['capo',1]]} ] },

  { name:'JAHRA ROAD', ar:'طريق الجهراء', theme:'highway', len:3200, tier:3,
    hint:'They blocked the road out.',
    gates:[{at:1100, type:'shutter', reward:{ability:'haymaker'}}],
    story:['Trucks across both lanes, sun going down behind the pylons.',
           'The road to the camp runs straight through them.'],
    storyAr:'الطريق مقطوع عند الجهراء',
    waves:[ {at:620,  e:[['bouncer',1],['runner',2]]},
            {at:1620, e:[['capo',1],['kicker',2]]},
            {at:2620, e:[['bouncer',2],['capo',1]]} ] },

  { name:'DESERT CAMP', ar:'مخيم البر', theme:'desert', len:3200, tier:3,
    hint:'The contenders wait by the fire.',
    gates:[{at:1150, type:'wall', reward:{ability:'hawk', xp:250}}],
    story:['The camp is where they pick who fights for the belt.',
           'Ahmed was never on the list. He is now.'],
    storyAr:'المخيم يختار من ينافس على الحزام',
    waves:[ {at:620,  e:[['kicker',2],['brawler',2]]},
            {at:1650, e:[['champ',1],['capo',1]]},
            {at:2650, e:[['champ',1],['grappler',1],['bouncer',1]]} ] },

  { name:'KUWAIT ARENA', ar:'بطولة الكويت', theme:'arena', len:1600, tier:4,
    hint:'Title fight. No way out.',
    story:['A full house, and AL-WAHSH waiting in the far corner.',
           'One fight between the souq kid and the belt.'],
    storyAr:'المواجهة الأخيرة مع الوحش',
    boss:true,
    waves:[ {at:420,  e:[['champ',2]]},
            {at:900,  e:[['boss',1]]} ] },

  // Unlocked after the title fight. Endless, so it has no exit and no length.
  { name:'SURVIVAL', ar:'البقاء', theme:'arena', len:1400, tier:0, survival:true,
    hint:'Endless waves. How far can Ahmed go?',
    story:['No belt, no crowd, no end. Just the next wave.'],
    storyAr:'موجات لا تنتهي',
    waves:[ {at:-1, e:[['thug',2]], tier:0} ] }
];
