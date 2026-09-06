/* AHMED — Kuwait Fighter
   HITS — every strike in the game.

   su/ac/rc are the startup, active and recovery windows in seconds: a hit
   only lands during `ac`, and `rc` is what makes a whiffed heavy hurt.
   `fam` decides which upgrade track scales it and which gates it can break.

   Loaded as a plain script before the game, so it works opened straight off
   disk with no build step and no server. Edit the numbers here; the game
   reads them and never keeps its own copy.
   ========================================================================== */
window.ASSET_HITS = {
  jab    :{fam:'box',  dmg:7,  su:.07, ac:.06, rc:.13, reach:54, push:70,  stam:5,  sfx:'punch', arm:'lead'},
  cross  :{fam:'box',  dmg:11, su:.10, ac:.07, rc:.19, reach:60, push:120, stam:8,  sfx:'punch', arm:'rear'},
  hook   :{fam:'box',  dmg:17, su:.14, ac:.08, rc:.26, reach:56, push:210, stam:12, sfx:'punch', arm:'rear', heavy:true},
  kick   :{fam:'kick', dmg:19, su:.16, ac:.09, rc:.28, reach:74, push:270, stam:14, sfx:'kick',  leg:true, heavy:true},
  knee   :{fam:'kick', dmg:23, su:.13, ac:.08, rc:.26, reach:42, push:160, stam:16, sfx:'kick',  leg:true, heavy:true},
  special:{fam:'kick', dmg:46, su:.18, ac:.26, rc:.34, reach:88, push:430, stam:0,  sfx:'kick',  leg:true, heavy:true, multi:true}
};
