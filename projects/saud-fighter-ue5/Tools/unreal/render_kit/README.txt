SAUD - RENDER KIT
=================

On a Mac? Use README_MAC.txt and RENDER_SAUD_MAC.command instead.

What this does
--------------
It renders the game's places in Unreal Engine 5 on your own PC and leaves
ONE zip file on your Desktop with the pictures and every log. You only
double-click one file. You send the zip back. That is all.

It makes 24 pictures: the open world, each of its nine districts, the souq
(fight, street, gate, the title shot), the prologue's gym and the monkey
island - from the same cameras as the Blender pictures already in
Docs\renders, so the two can be compared.


What your PC needs
------------------
1. Unreal Engine 5.4, from the Epic Games Launcher (Unreal Engine tab,
   Library, + next to Engine Versions, pick 5.4).
2. Visual Studio 2022 (the free Community edition is fine). In its
   installer, tick "Game development with C++". That also installs the
   Windows SDK the game needs.
3. About 40 GB free on the drive the game folder is on.
4. A graphics card (NVIDIA, AMD or Intel Arc, with up-to-date drivers).
5. The internet, the first time (the kit downloads one small helper for
   Unreal's Python, called numpy).


How to get the game onto the PC
-------------------------------
1. On the project's GitHub page, switch to the branch
   claude/ahmed-mobile-game-87gx8c, press the green "Code" button, then
   "Download ZIP".
2. Right-click the downloaded zip, "Extract All...", and extract it to a
   SHORT folder, for example C:\SAUD. (Unreal can fail when a folder path
   is very long, and the Downloads folder makes it long.)
3. Open C:\SAUD. Inside it is one folder with a long name (it starts with
   ui-ux-pro-max-skill). Right-click it, Rename, and call it just  g
   so the game sits at C:\SAUD\g\projects\saud-fighter-ue5. Unreal adds
   long folder names of its own while it builds, and Windows refuses
   paths over 260 letters.
4. Open g, then projects, then saud-fighter-ue5, then Tools, then unreal,
   then render_kit.
5. Double-click RENDER_SAUD.bat.

If Windows shows "Windows protected your PC", press "More info", then
"Run anyway".


What happens, and how long it takes
-----------------------------------
A black window opens and says "STEP 1 of 6", "STEP 2 of 6" and so on.
Leave it open.

  Step 1  finds Unreal 5.4 and the game                 seconds
  Step 2  checks Visual Studio, the SDK and disk space   seconds
  Step 3  builds the game code                          10 - 40 minutes
  Step 4  sets the maps and materials up in Unreal       30 - 90 minutes
          (only the first time; nothing seems to happen for a long while,
          that is normal)
  Step 5  renders the pictures (Unreal's window opens;   20 - 90 minutes
          do not close it - it closes by itself)
  Step 6  makes the zip on your Desktop                 a minute

The very first run can take two to three hours in all, most of it Unreal
compiling its shaders. Later runs are much shorter: the build is quick
when nothing changed, and step 4 is skipped (press R when it asks if you
want to redo it).


What to send back
-----------------
The zip on your Desktop, named like SaudRenders_2026-10-14_21-30.zip. When
the kit finishes it opens the folder with the zip selected, and the
window says "Send this file back:" with its full path.

Send it back EVEN IF SOMETHING FAILED. The game code has never been built
before, so on the very first run step 3 is expected to fail. That is not
your mistake: the kit then stops, still makes the zip, and the build log
inside it is exactly what is needed to fix the code.


If it stops
-----------
The window says what is missing in plain words (for example, Visual
Studio's C++ tools) and still makes the zip. Fix that one thing and
double-click RENDER_SAUD.bat again.
