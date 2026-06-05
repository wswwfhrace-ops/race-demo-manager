# race-demo-manager
Automatic PB demo tracker for Warfork and Warsow. Supports wf and wsw on both linux and windows.

# Requirements
Python

# Installation
git clone https://github.com/yourname/demo-manager.git

This folder can be anywhere, so place it in a convinient location.

# Running
On first launch
- Enter player name
- Choose the correct demo folders (Users with fs_usehomedir 0 will need to enter their path manually)
- Select your restart and noclip toggle binds (use the same binds you have already been using)

The script will create a demomanager.cfg and append a exec demomanager.cfg to the bottom of your autoexec.cfg.
It will also automatically create the below file structure in the wf and wsw demo folders.

demo manager/

├── demos/

├── unprocessed demos/

└── invalid demos/

If you have demos from when you used mikul's tool or if you have demos that only contain 1 run. You can copy them into demo manager/unprocessed demos/ in either wf/wsw depending on the demo and the script will parse them and save the times and demos. This can be done at anytime, you just need to restart the program.

# Ensuring it works
Each time you restart the race using the bind, the console should should show this
- Recording demo: demos/run00.wfdz22
- [wf-demos] recording run_00
- Stopped demo: demos/run_00.wfdz22
- Recording demo: demos/run01.wfdz22
- etc


The cmd window should show this

Run not completed
- [warfork] New run:  run_01.wfdz22
- [warfork] Previous: run_00.wfdz22
- Checking run_00.wfdz22
- Not a completed run


Run completed (new map or new pb)
- Checking run_01.wfdz22
- Map:  map_name
- Time: time_of_run
- Previous PB: time_of_previous_pb
- Improvement: -15.435s
- *** NEW PB! ***
- Saved as: testmap [99.77.33] WF by Player 05-06-2026.wfdz22


Run completed but not pb
- Checking run_01.wfdz22
- Map:  map_name
- Time: time_of_run
- Not a PB  (best: time_of_previous_pb)



# How it works
The script watches the rotating run slots. when a new slot begins recording, the previous slot is checked for a pb.

If a pb is found, the demo is renamed and saved and the records are updated.

Demos will be renamed in this format mapname [time] game_name by player_name date

eg: testmap [99.77.33] WSW by Player 05-06-2026.wdz20

# Records
records will be stored in the race-demo-manager folder as records_wf.json, records_wsw.json, records_all.json
