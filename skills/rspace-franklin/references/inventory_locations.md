# Lab inventory: storage and location

*[EDIT ME]* This file is a placeholder. Replace the examples below with your lab's actual top-level containers and where things are kept, to provide shortcuts for the assistant. Optionally, you can also create a separate memory for your Lab inventory and let the agent update it regularly.

Delete the examples once you've added your own.

---

## Top-level containers (replace this)

The root containers to start browsing from. Give each one's RSpace Global ID so the assistant can jump straight to it rather than searching by name.

| Top-level container    | Global ID | Contains                     |
| ----------------------- | --------- | ---------------------------- |
| Life Sciences Building | IC1001    | Room 214, Room 210, Room 108 |
| Room 214               | IC1002    | Freezer 3, Liquid N2 Tank 1  |
| Room 210               | IC1003    | Freezer 2                    |
| Room 108               | IC1004    | Chemical store, Stockroom    |

## Item locations (replace this)

| Item type            | Where to find existing stock              | Global ID | Where to place a new one                                          |
| --------------------- | ----------------------------------------- | --------- | ------------------------------------------------------------------ |
| DNA / RNA samples    | Freezer 3 (-80°C), Room 214               | IC2001    | Next open box slot in Freezer 3                                   |
| Frozen cell lines    | Liquid N2 Tank 1, Room 214                | IC2002    | Next open position in Tank 1; note passage number and freeze date |
| Protein samples      | Freezer 2 (-20°C), Room 210               | IC2003    | Next open box slot in Freezer 2                                   |
| Chemicals / reagents | Chemical store, Room 108, by hazard class | IC2004    | Shelf matching the reagent's hazard class                         |
| Consumables          | Stockroom, Room 108                       | IC2005    | Labelled shelf bin for that consumable                            |
