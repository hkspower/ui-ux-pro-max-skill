SAUD - REPAIR KIT FOR A MAC
===========================

What this does
--------------
When the game will not open, will not build, or Unreal says the project
is "out of date" or "missing modules", this repairs it in one go and
leaves ONE zip on your Desktop with every log. You double-click one file
and send the zip back. That is all.

It does the same eight steps as the Windows kit:

  Step 1  finds Unreal Engine 5.4 and the game              seconds
  Step 2  checks this Mac: Unreal closed, Xcode, free space  seconds
  Step 3  checks the game's files                            seconds
  Step 4  moves the old build folders aside (Binaries,       seconds
          Intermediate, DerivedDataCache, the Xcode workspace)
  Step 5  makes the Xcode project files again                a minute
  Step 6  rebuilds the game code from nothing                10 - 40 minutes
  Step 7  sets the maps and materials up again in Unreal     30 - 90 minutes
          (type S and Return when it asks to skip this; it
          does it by itself after 30 seconds)
  Step 8  makes the zip on your Desktop                      a minute

Nothing of the game is deleted. The old build folders are MOVED to
Saved/RepairKit/old_<date> inside the game's folder. Once the game opens,
delete that old_ folder to free the space. The next repair removes it by
itself before it moves the new ones.


Before you start
----------------
- Quit Unreal (save your work first) and Xcode. The kit stops and says so
  if Unreal is still open.
- You need what the Mac render kit needs: Unreal Engine 5.4, the full
  Xcode app (opened once), and about 40 GB free. Keep the Mac plugged in.


How to run it
-------------
Open the game's folder, then Tools, then unreal, then repair_kit.
The first time only: right-click REPAIR_SAUD_MAC.command, choose Open,
and press Open again when macOS warns that it is from the internet.
After that, a double-click is enough.

If macOS says it "cannot be opened": open Terminal, type  bash  and a
space, drag REPAIR_SAUD_MAC.command into the window, and press Return.
To skip the long step 7, add  quick  after it before pressing Return.


What to send back
-----------------
The zip on your Desktop, named like SaudRepair_2026-11-01_21-30.zip (the
time is Riyadh time). Send it back EVEN IF SOMETHING FAILED.

The last lines in the window say how it went:
  REPAIRED   the code was rebuilt. Open SaudFighter.uproject.
  REBUILT, BUT ...  it built, but some of the game's files are damaged;
             the window and logs/files_report.txt name them. Get those
             files again from the branch.
  STOPPED    something is missing; the line says what, in plain words.
             Fix that one thing and double-click the file again.
