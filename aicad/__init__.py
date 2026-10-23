"""aicad: small, reusable helpers for AI-agent-written parametric 3D prints.

Modules:
    mesh       manifold3d <-> trimesh, load_mesh, mesh_report (watertight, bodies), sections
    ppi_hinge  captive print-in-place hinge that splits any solid in two
    checks     ray clearances, swing / pose collision sweeps (re-exports thickness)
    thickness  thin_walls (XY width) and z_thickness (Z thickness): per-piece
               findings, sliver filter, named zones
    sweep2d    2D side-view mechanism sweep with shapely (before any 3D CAD)
    coupons    test-piece builders: hole gauge strip, 3-link hinge chain
    label      embossed / engraved text labels
    export     STL / 3MF writers that re-read their output, plate check,
               verification.json writer
    preview    matplotlib-only preview PNGs (3D view + sections)
"""
__version__ = "0.1.0"
