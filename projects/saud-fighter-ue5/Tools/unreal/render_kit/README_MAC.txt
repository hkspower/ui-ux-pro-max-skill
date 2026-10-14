SAUD - RENDER KIT FOR A MAC
===========================

What this does
--------------
It renders the game's places in Unreal Engine 5 on your MacBook and leaves
ONE zip file on your Desktop with the pictures and every log. You only
double-click one file. You send the zip back. That is all.

It makes the same 24 pictures as the Windows kit: the open world, each of
its nine districts, the souq (fight, street, gate, the title shot), the
prologue's gym and the monkey island, from the same cameras as the Blender
pictures already in Docs/renders, so the two can be compared.


What your Mac needs
-------------------
1. An Apple Silicon MacBook (M1, M2, M3 or M4) on the newest macOS it
   takes.
2. Unreal Engine 5.4. Install the Epic Games Launcher for Mac from
   epicgames.com, sign in, open the Unreal Engine tab, then Library, press
   + next to Engine Versions and pick 5.4. Unreal itself is about 60 GB.
3. Xcode, free from the Mac App Store. After it installs, open Xcode once
   and let it finish installing its parts, then quit it. (Unreal uses
   Xcode to build the game code. The small "command line tools" alone are
   not enough.)
4. About 40 GB free besides Unreal itself.
5. The internet, the first time (the kit downloads one small helper for
   Unreal's Python, called numpy).


How to get the game onto the Mac
--------------------------------
1. On the project's GitHub page, switch to the branch
   claude/ahmed-mobile-game-87gx8c, press the green "Code" button, then
   "Download ZIP".
2. Double-click the downloaded zip. Drag the folder it makes into your
   home folder (the one with your name, in Finder's sidebar), not into
   Desktop, Documents or Downloads: macOS keeps asking permission for
   those, and the long folder name gets in the way.
3. Rename that folder (its name starts with ui-ux-pro-max-skill) to just
   g
4. Open g, then projects, then saud-fighter-ue5, then Tools, then unreal,
   then render_kit.
5. The first time only: right-click RENDER_SAUD_MAC.command, choose Open,
   and press Open again when macOS warns that it is from the internet.
   After that, a double-click is enough.

If macOS says it "cannot be opened", or nothing happens: open Terminal
(Applications, Utilities), type  bash  and a space, drag
RENDER_SAUD_MAC.command into the Terminal window, and press Return.


What happens, and how long it takes
-----------------------------------
A Terminal window opens and says "STEP 1 of 6", "STEP 2 of 6" and so on.
Leave it open, and keep the MacBook plugged in and awake.

  Step 1  finds Unreal 5.4 and the game                 seconds
  Step 2  checks Xcode and disk space                   seconds
  Step 3  builds the game code                          10 - 40 minutes
  Step 4  sets the maps and materials up in Unreal       30 - 90 minutes
          (only the first time; nothing seems to happen for a long while,
          that is normal)
  Step 5  renders the pictures (Unreal's window opens;   20 - 90 minutes
          do not close it - it closes by itself)
  Step 6  makes the zip on your Desktop                 a minute

The very first run can take two to three hours in all, most of it Unreal
compiling its shaders. Later runs are much shorter: the build is quick
when nothing changed, and step 4 is skipped unless you press R when it
asks.

If the kit cannot find Unreal by itself, it asks: drag the UE_5.4 folder
(usually in /Users/Shared/Epic Games) into the Terminal window and press
Return.


What to send back
-----------------
The zip on your Desktop, named like SaudRenders_2026-10-14_21-30.zip (the
time is Riyadh time). When the kit finishes it shows the zip in Finder,
and the window says "Send this file back:" with its full path.

Send it back EVEN IF SOMETHING FAILED. The game code has never been built
before, so on the very first run step 3 is expected to fail. That is not
your mistake: the kit then stops, still makes the zip, and the build log
inside it is exactly what is needed to fix the code.


If it stops
-----------
The window says what is missing in plain words (for example, Xcode) and
still makes the zip. Fix that one thing and double-click
RENDER_SAUD_MAC.command again.
