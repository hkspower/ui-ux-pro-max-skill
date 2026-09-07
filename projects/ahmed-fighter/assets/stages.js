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
  { name:'SOUQ MUBARAKIYA', ar:'سوق المباركية', theme:'souq', len:3000, tier:0,
    hint:'Trouble in the old market.',
    gates:[{at:1150, type:'wall', reward:{xp:450}}],
    story:['A crew has been leaning on the traders in the old souq for months.',
           'Ahmed grew up in these alleys. Tonight he stops being a bystander.'],
    storyAr:'بدأت الحكاية في سوق المباركية',
    /* He has only just landed. The first wave is almost immediate -- the
       souq does not give him time to work out where he is. */
    waves:[ {at:300,  e:[['thug',2]]},
            {at:1250, e:[['thug',2],['brawler',1]]},
            {at:2350, e:[['brawler',2],['thug',1]]} ] },

  { name:'SALMIYA GYM', ar:'نادي السالمية', theme:'gym', len:2600, tier:0,
    hint:'Spar your way through the club.',
    gates:[{at:2000, type:'stash', reward:{ability:'vault'}}],
    story:['Word travels. The Salmiya club wants to see what the souq kid can do.',
           'Six rounds, no headgear, and nobody is holding back.'],
    storyAr:'الاختبار الأول في نادي السالمية',
    /* Six short rounds with barely a walk between them, because the story
       text has always said six rounds and the stage used to give three. */
    waves:[ {at:280,  e:[['thug',1]]},
            {at:680,  e:[['brawler',1]]},
            {at:1080, e:[['kicker',1],['thug',1]]},
            {at:1480, e:[['brawler',2]]},
            {at:1880, e:[['kicker',2]]},
            {at:2250, e:[['kicker',1],['brawler',2]]} ] },

  { name:'SHARQ FISH MARKET', ar:'سوق شرق للسمك', theme:'fishmarket', len:3600, tier:1,
    hint:'Dawn on the harbour. They came early.',
    gates:[{at:1050, type:'ledge', reward:{ability:'dashleap'}}],
    story:['The crew moved their business to the harbour before sunrise.',
           'Wet stone, cold air, and runners who will not stand still.'],
    storyAr:'الفجر على الميناء',
    /* The longest area in the game and only three ambushes in it. Runners
       break and regroup, so the harbour is mostly walking and watching. */
    waves:[ {at:700,  e:[['runner',2],['thug',1]]},
            {at:2000, e:[['runner',2],['brawler',2]]},
            {at:3250, e:[['bouncer',1],['runner',2]]} ] },

  { name:'KUWAIT TOWERS', ar:'أبراج الكويت', theme:'towers', len:2800, tier:1,
    hint:'Night raid on the waterfront.',
    gates:[{at:1600, type:'wall', reward:{xp:500}}],
    story:['They want the waterfront cleared before the season opens.',
           'Ahmed gets there first.'],
    storyAr:'ليلة على الواجهة البحرية',
    /* A raid, not a patrol: two large contacts with a long quiet between,
       and the cache sits in the middle of that quiet. */
    waves:[ {at:800,  e:[['kicker',2],['brawler',2],['thug',1]]},
            {at:2200, e:[['grappler',1],['kicker',2],['brawler',1]]} ] },

  { name:'MARINA CRESCENT', ar:'مارينا كريسنت', theme:'marina', len:2200, tier:2,
    hint:'AL-SAQR runs this strip.',
    gates:[{at:950, type:'gap', reward:{ability:'powerkick'}}],
    story:['The neon strip belongs to AL-SAQR — the Falcon. All legs, no patience.',
           'Beat him and the crew loses its enforcer.'],
    storyAr:'الصقر يحرس المارينا',
    boss:true,
    /* Tightest area in the game. Two contacts close together and then him,
       because a boss strip should feel like a corridor closing. */
    waves:[ {at:450,  e:[['capo',1],['runner',2]]},
            {at:1150, e:[['bouncer',1],['capo',1]]},
            {at:1900, e:[['saqr',1]]} ] },

  { name:'FAILAKA ISLAND', ar:'جزيرة فيلكا', theme:'failaka', len:2500, tier:2,
    hint:'Grapplers hold the ruins.',
    gates:[{at:2150, type:'shutter', reward:{xp:600}}],
    story:['They regrouped on the island, among the old stone.',
           'Nowhere to run out here — which cuts both ways.'],
    storyAr:'بين آثار فيلكا',
    /* Short and packed. "Nowhere to run out here" should be true of the
       stage and not only of the line -- there is no long walk anywhere. */
    waves:[ {at:500,  e:[['grappler',1],['brawler',1]]},
            {at:1200, e:[['grappler',2],['kicker',1]]},
            {at:1850, e:[['grappler',2],['capo',1]]} ] },

  { name:'JAHRA ROAD', ar:'طريق الجهراء', theme:'highway', len:3400, tier:3,
    hint:'They blocked the road out.',
    gates:[{at:1100, type:'shutter', reward:{ability:'haymaker'}}],
    story:['Trucks across both lanes, sun going down behind the pylons.',
           'The road to the camp runs straight through them.'],
    storyAr:'الطريق مقطوع عند الجهراء',
    /* Five small blocks at even spacing. The road is not an ambush, it is a
       queue of them, and the evenness is the point. */
    waves:[ {at:600,  e:[['runner',2]]},
            {at:1250, e:[['bouncer',1],['runner',1]]},
            {at:1900, e:[['capo',1],['kicker',1]]},
            {at:2500, e:[['bouncer',1],['kicker',1]]},
            {at:3050, e:[['bouncer',1],['capo',1]]} ] },

  { name:'DESERT CAMP', ar:'مخيم البر', theme:'desert', len:3000, tier:3,
    hint:'The contenders wait by the fire.',
    gates:[{at:1150, type:'wall', reward:{ability:'hawk', xp:250}}],
    story:['The camp is where they pick who fights for the belt.',
           'Ahmed was never on the list. He is now.'],
    storyAr:'المخيم يختار من ينافس على الحزام',
    /* Two fights, both heavy. The camp is not a patrol route -- it is where
       the contenders are sitting, and they get up together. */
    waves:[ {at:900,  e:[['kicker',2],['brawler',2],['capo',1]]},
            {at:2300, e:[['champ',2],['grappler',1]]} ] },

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
