# Example: KiCad board → SmartDrill Pro

This folder is a complete, tiny example you can use immediately.

## What is in here

- `kicad/simple_board.kicad_pro`, `.kicad_sch`, `.kicad_pcb` — the KiCad source project.
- `F_Cu.gtl`, `B_Cu.gbl`, `F_Mask.gts`, `B_Mask.gbs`, `Edge_Cuts.gm1` — exported Gerber files.
- `PTH.drl`, `NPTH.drl` — exported Excellon drill files.
- `simple_board_gbr.zip` — all manufacturing files zipped for one-click import into SmartDrill Pro.

The board is a 12 mm × 12 mm coupon with:

- a 0.25 mm front-copper loop,
- 2 × 0.8 mm plated holes,
- 1 × 1.5 mm plated hole,
- 1 × 2.0 mm non-plated mounting hole.

The exported files were created to match this PCB. No fake G-code is included.

## A. If you just want to try SmartDrill Pro now

1. Open SmartDrill Pro.
2. Go to **New PCB Project** → create a project, for example `Example Board`.
3. Go to **File Manager** → **Import** → select `simple_board_gbr.zip`.
4. Confirm the layer list shows front copper, outline, plated drill and non-plated drill.
5. Go to **PCB Viewer** to see the real geometry.
6. Go to **CAM Processing** → leave the conservative defaults (or adjust for your tool) → generate.
7. Go to **G-code Preview** → load a generated `.nc` → check `SAFE` → **Create validated copy**.
8. Go to **Machine Control** → stay in **Simulation** → select `*.validated.nc` → tick confirmation → **Run**.

That is the full software workflow. No machine is touched in simulation.

## B. How the Gerber/Excellon files were made from KiCad

Open `kicad/simple_board.kicad_pro` in KiCad 8/9/10.

### 1. Plot Gerbers

1. **File → Plot…**
2. **Plot format:** Gerber (`.gbr`/Gerber X2 is fine).
3. Select layers:
   - `F.Cu`
   - `B.Cu`
   - `F.Mask`
   - `B.Mask`
   - `Edge.Cuts`
4. In the general plot options:
   - uncheck **Plot on all layers** if enabled,
   - keep **Use auxiliary axis as origin** unchecked,
   - set output directory to the `simple_board` folder.
5. Click **Plot**.

KiCad may name files `simple_board-F_Cu.gbr` etc. SmartDrill Pro classifies by filename, so rename them to the simple names used here if needed:

| KiCad output | File in this example |
| --- | --- |
| `*-F_Cu.gbr` | `F_Cu.gtl` |
| `*-B_Cu.gbr` | `B_Cu.gbl` |
| `*-F_Mask.gbr` | `F_Mask.gts` |
| `*-B_Mask.gbr` | `B_Mask.gbs` |
| `*-Edge_Cuts.gbr` | `Edge_Cuts.gm1` |

The `.gtl/.gbl/.gts/.gbs/.gm1` names are the classic Gerber extensions and are what our sample uses.

### 2. Generate drill files

1. **File → Fabrication Outputs → Drill Files…**
2. **Output format:** Excellon.
3. Choose:
   - **PTH** (plated holes) → save as `PTH.drl`.
   - **NPTH** (non-plated holes) → save as `NPTH.drl`.
4. Use metric units and 3:3 format if asked.

### 3. Zip them

Select all `.gtl/.gbl/.gts/.gbs/.gm1/.drl` files and zip them as `simple_board_gbr.zip`. Do not include the `.kicad_*` source files unless you want them copied too; SmartDrill Pro will ignore non-manufacturing files.

## C. What SmartDrill Pro does with them

- Gerbonara parses the Gerber/Excellon content.
- The layer classifier identifies copper, mask, outline and drill files.
- PCB Viewer renders the real geometry.
- FlatCAM writes real toolpaths from those files.
- G-code Preview validates and creates a `*.validated.nc` copy.
- Machine Control only runs that validated copy after you explicitly confirm.

## Safety

This example is for learning the software flow. The CAM defaults are conservative starting values, not cutting instructions. Real machine setup remains UNVERIFIED until you calibrate and test it yourself.
