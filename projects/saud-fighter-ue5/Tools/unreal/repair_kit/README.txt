SAUD - REPAIR KIT
=================

On a Mac? Use README_MAC.txt and REPAIR_SAUD_MAC.command instead.

What this does
--------------
When the game will not open, will not build, or Unreal says the project
is "out of date" or "missing modules", this repairs it in one go and
leaves ONE zip on your Desktop with every log. You double-click one file
and send the zip back. That is all.

It does eight steps:

  Step 1  finds Unreal Engine 5.4 and the game              seconds
  Step 2  checks this PC: Unreal closed, Visual Studio 2022  seconds
          with C++, the Windows SDK, free disk space
  Step 3  checks the game's files: the project file, the     seconds
          code's build files, the settings, the data tables,
          and any file that is empty or did not download
  Step 4  moves the old build folders aside (Binaries,       seconds
          Intermediate, DerivedDataCache, .vs, the .sln)
  Step 5  makes the Visual Studio project files again        a minute
  Step 6  rebuilds the game code from nothing                10 - 40 minutes
  Step 7  sets the maps and materials up again in Unreal     30 - 90 minutes
          (press S when it asks to skip this; it does it
          by itself after 30 seconds)
  Step 8  makes the zip on your Desktop                      a minute

Nothing of the game is deleted. The old build folders are MOVED to
Saved\RepairKit\old_<date> inside the game's folder. Unreal makes new
ones. Once the game opens, delete that old_ folder to free the space.
The next repair removes it by itself before it moves the new ones.


Before you start
----------------
- Close Unreal (save your work first) and Visual Studio. The kit stops and
  says so if Unreal is still open.
- You need what the render kit needs: Unreal Engine 5.4, Visual Studio
  2022 with "Game development with C++", and about 40 GB free.


How to run it
-------------
Open the game's folder, then Tools, then unreal, then repair_kit, and
double-click REPAIR_SAUD.bat. If Windows shows "Windows protected your
PC", press "More info", then "Run anyway".

To skip the long step 7, open a command prompt in that folder and type:
    REPAIR_SAUD.bat quick


What to send back
-----------------
The zip on your Desktop, named like SaudRepair_2026-11-01_21-30.zip (the
time is Riyadh time). Send it back EVEN IF SOMETHING FAILED: the build
log inside it is exactly what is needed to fix the code.

The last lines in the window say how it went:
  REPAIRED   the code was rebuilt. Open SaudFighter.uproject.
  REBUILT, BUT ...  it built, but some of the game's files are damaged;
             the window and logs\files_report.txt name them. Get those
             files again from the branch.
  STOPPED    something is missing; the line says what, in plain words.
             Fix that one thing and double-click the file again.
