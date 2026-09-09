/* AHMED — Kuwait Fighter: offline cache.
   Bump CACHE when index.html changes so players get the new build. */
var CACHE = 'ahmed-kuwait-fighter-v26';
var FILES = ['./', './index.html', './manifest.webmanifest', './icon.svg',
             // Game data. Miss one of these and the game throws on start
             // rather than running with an empty table, so they are cached
             // with the same weight as index.html itself.
             './assets/colors.js', './assets/ahmed.js', './assets/enemies.js', './assets/hits.js',
             './assets/talents.js', './assets/upgrades.js', './assets/weapons.js', './assets/levels.js',
             './assets/world.js', './assets/stages.js'];

self.addEventListener('install', function(e){
  e.waitUntil(caches.open(CACHE).then(function(c){ return c.addAll(FILES); }).then(function(){
    return self.skipWaiting();
  }));
});

self.addEventListener('activate', function(e){
  e.waitUntil(caches.keys().then(function(keys){
    return Promise.all(keys.map(function(k){ return k === CACHE ? null : caches.delete(k); }));
  }).then(function(){ return self.clients.claim(); }));
});

self.addEventListener('fetch', function(e){
  if(e.request.method !== 'GET') return;
  e.respondWith(
    fetch(e.request).then(function(res){
      var copy = res.clone();
      caches.open(CACHE).then(function(c){ c.put(e.request, copy); }).catch(function(){});
      return res;
    }).catch(function(){
      return caches.match(e.request).then(function(hit){
        return hit || caches.match('./index.html');
      });
    })
  );
});
