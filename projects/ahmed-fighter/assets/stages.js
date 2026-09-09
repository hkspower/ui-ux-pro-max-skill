/* AHMED — Kuwait Fighter
   STAGES — the nine places of AL-HALQA, plus survival.

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
  { name:'SOUQ AL-DAWAR', ar:'سوق الدوار', theme:'souq', len:3000, tier:0,
    hint:'Ask about the hole. Nobody looks up.',
    gates:[{at:1150, type:'wall', reward:{xp:450}}],
    story:['He asks where the hole is. Nobody understands the question.',
           'A crew leans on the traders. He steps in. It is the only thing he knows.'],
    storyAr:'يسأل عن الحفرة، ولا أحد يفهم',
    /* He has only just landed. The first wave is almost immediate -- the
       souq does not give him time to work out where he is. */
    waves:[ {at:300,  e:[['thug',2]]},
            {at:1250, e:[['thug',2],['brawler',1]]},
            {at:2350, e:[['brawler',2],['thug',1]]} ] },

  { name:'BAYT AL-DARB', ar:'بيت الضرب', theme:'gym', len:2600, tier:0,
    hint:'Six rounds. They want to see him.',
    gates:[{at:2000, type:'stash', reward:{ability:'vault'}}],
    story:['Word travels. The striking house wants to see what the stranger can do.',
           'Six rounds. Then they hand him VAULT. He takes it for a way up.'],
    storyAr:'ست جولات، والبيت كله يراقب',
    /* Six short rounds with barely a walk between them, because the story
       text has always said six rounds and the stage used to give three. */
    waves:[ {at:280,  e:[['thug',1]]},
            {at:680,  e:[['brawler',1]]},
            {at:1080, e:[['kicker',1],['thug',1]]},
            {at:1480, e:[['brawler',2]]},
            {at:1880, e:[['kicker',2]]},
            {at:2250, e:[['kicker',1],['brawler',2]]} ] },

  { name:'MARSA AL-FAJR', ar:'مرسى الفجر', theme:'fishmarket', len:3600, tier:1,
    hint:'Dawn. Runners who will not stand still.',
    gates:[{at:1050, type:'ledge', reward:{ability:'dashleap'}}],
    story:['Dawn on the water. The stone is wet and the runners will not stand still.',
           'The next rung sits behind a fight. So will the one after.'],
    storyAr:'فجر على الماء، وخصوم لا يثبتون',
    /* The longest area in the game and only three ambushes in it. Runners
       break and regroup, so the harbour is mostly walking and watching. */
    waves:[ {at:700,  e:[['runner',2],['thug',1]]},
            {at:2000, e:[['runner',2],['brawler',2]]},
            {at:3250, e:[['bouncer',1],['runner',2]]} ] },

  { name:'ABRAJ AL-MALIH', ar:'أبراج المالح', theme:'towers', len:2800, tier:1,
    hint:'Night. A raid, not a patrol.',
    gates:[{at:1600, type:'wall', reward:{xp:500}}],
    story:['Night on the salt towers. This is a raid, not a patrol.',
           'He takes it tower by tower. He thinks he is working his way out.'],
    storyAr:'غارة ليلية على أبراج المالح',
    /* A raid, not a patrol: two large contacts with a long quiet between,
       and the cache sits in the middle of that quiet. */
    waves:[ {at:800,  e:[['kicker',2],['brawler',2],['thug',1]]},
            {at:2200, e:[['grappler',1],['kicker',2],['brawler',1]]} ] },

  { name:'AL-HILAL', ar:'الهلال', theme:'marina', len:2200, tier:2,
    hint:'AL-SAQR runs the crescent.',
    gates:[{at:950, type:'gap', reward:{ability:'powerkick'}}],
    story:['AL-SAQR runs the neon crescent. He is all legs and no patience.',
           'He fell too, a long time ago. He says so once. Ahmed does not hear it.'],
    storyAr:'الصقر سقط قبله، وكف عن السؤال',
    boss:true,
    /* Tightest area in the game. Two contacts close together and then him,
       because a boss strip should feel like a corridor closing. */
    waves:[ {at:450,  e:[['capo',1],['runner',2]]},
            {at:1150, e:[['bouncer',1],['capo',1]]},
            {at:1900, e:[['saqr',1]]} ] },

  { name:'JAZIRAT AL-HAJAR', ar:'جزيرة الحجر', theme:'failaka', len:2500, tier:2,
    hint:'Grapplers hold the stone.',
    gates:[{at:2150, type:'shutter', reward:{xp:600}}],
    story:['They fall back to the stone island. Grapplers hold the ruins.',
           'There is nowhere to run out here. That cuts both ways.'],
    storyAr:'لا مهرب هنا، لا لهم ولا له',
    /* Short and packed. "Nowhere to run out here" should be true of the
       stage and not only of the line -- there is no long walk anywhere. */
    waves:[ {at:500,  e:[['grappler',1],['brawler',1]]},
            {at:1200, e:[['grappler',2],['kicker',1]]},
            {at:1850, e:[['grappler',2],['capo',1]]} ] },

  { name:'AL-TARIQ AL-MASDUD', ar:'الطريق المسدود', theme:'highway', len:3400, tier:3,
    hint:'The road is blocked. Walk it anyway.',
    gates:[{at:1100, type:'shutter', reward:{ability:'haymaker'}}],
    story:['The road is dead. Trucks sit across both lanes and the sun is going down.',
           'It is not one fight. It is a queue of them. He takes his place in it.'],
    storyAr:'الطريق مقطوع ولا طريق غيره',
    /* Five small blocks at even spacing. The road is not an ambush, it is a
       queue of them, and the evenness is the point. */
    waves:[ {at:600,  e:[['runner',2]]},
            {at:1250, e:[['bouncer',1],['runner',1]]},
            {at:1900, e:[['capo',1],['kicker',1]]},
            {at:2500, e:[['bouncer',1],['kicker',1]]},
            {at:3050, e:[['bouncer',1],['capo',1]]} ] },

  { name:'MUKHAYYAM AL-NIRAN', ar:'مخيم النيران', theme:'desert', len:3000, tier:3,
    hint:'The contenders wait by the fires.',
    gates:[{at:1150, type:'wall', reward:{ability:'hawk', xp:250}}],
    story:['Here they pick who fights for the belt. He was never on the list. He is now.',
           'The last wall gives him HAWK FIST, fire in his hands. West is the souq.'],
    storyAr:'نار في يديه، والحلقة تكتمل',
    /* Two fights, both heavy. The camp is not a patrol route -- it is where
       the contenders are sitting, and they get up together. */
    waves:[ {at:900,  e:[['kicker',2],['brawler',2],['capo',1]]},
            {at:2300, e:[['champ',2],['grappler',1]]} ] },

  { name:'AL-HALQA', ar:'الحلقة', theme:'arena', len:1600, tier:4,
    hint:'The door his hands fit. No way up.',
    story:['The door off the souq opens to his new hands. It is not the way up.',
           'The house is full. It knows his name. AL-WAHSH waits in the far corner.'],
    storyAr:'الحلقة تعرف اسمه، والوحش ينتظر',
    boss:true,
    waves:[ {at:420,  e:[['champ',2]]},
            {at:900,  e:[['boss',1]]} ] },

  // Unlocked after the title fight. Endless, so it has no exit and no length.
  { name:'BILA NIHAYA', ar:'بلا نهاية', theme:'arena', len:1400, tier:0, survival:true,
    hint:'No end. Just the next wave.',
    story:['No belt, no crowd, no end. Just the next wave.'],
    storyAr:'لا حزام ولا جمهور ولا نهاية',
    waves:[ {at:-1, e:[['thug',2]], tier:0} ] }
];
