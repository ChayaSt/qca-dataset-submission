import os
import json
import tarfile
import tqdm

import qcportal as ptl
import qcelemental as qcel
from qcelemental.models import Molecule

collection_name = "OpenFF Gen 2 Torsion Set 2 Coverage"
UPDATE = False


def read_selected_torsions(input_json):
    """ Read data generated by select_torsions.py
    Returns
    -------
    selected_torsions: dict
        Dictionary for selected torsions, has this structure:
        {
            canonical_torsion_index1: {
                'initial_molecules': [ Molecule1a, Molecule1b, .. ],
                'atom_indices': [ (0,1,2,3) ],
                'attributes': {'canonical_explicit_hydrogen_smiles': .., 'canonical_isomeric_smiles': .., ..}
            },
            ..
        }
    """
    with open(input_json) as infile:
        selected_torsions = json.load(infile)
    return selected_torsions


print("Reading selected_torsions...")

if not os.path.exists("coverage_selected_torsions.json"):
    with tarfile.open("coverage_selected_torsions.json.tar.gz") as f:
        f.extractfile("coverage_selected_torsions.json")
selected_torsions = read_selected_torsions("coverage_selected_torsions.json")


print(f"Found {len(selected_torsions)} torsions")

print("Initializing dataset...")
# client = ptl.FractalClient("localhost:7777", verify=False)
client = ptl.FractalClient.from_file()

if UPDATE:
    ds = client.get_collection("TorsionDriveDataset", collection_name)
else:
    # create a new dataset with specified name
    ds = ptl.collections.TorsionDriveDataset(collection_name, client=client)

    # create specification for this dataset
    opt_spec = {
        "program": "geometric",
        "keywords": {
            "coordsys": "tric",
            "enforce": 0.1,
            "reset": True,
            "qccnv": True,
            "epsilon": 0.0,
        },
    }
    kw = ptl.models.KeywordSet(
        values={
            "maxiter": 200,
            "scf_properties": [
                "dipole",
                "quadrupole",
                "wiberg_lowdin_indices",
                "mayer_indices",
            ],
        }
    )
    kw_id = client.add_keywords([kw])[0]

    qc_spec = {
        "driver": "gradient",
        "method": "B3LYP-d3bj",
        "basis": "dzvp",
        "program": "psi4",
        "keywords": kw_id,
    }
    ds.add_specification(
        "default",
        opt_spec,
        qc_spec,
        description="Standard OpenFF torsiondrive specification.",
    )

# add molecules
print(f"Adding {len(selected_torsions)} torsions")
i = 0

for canonical_torsion_index, torsion_data in tqdm.tqdm(selected_torsions.items()):

    attributes = torsion_data["attributes"]
    torsion_atom_indices = torsion_data["atom_indices"]
    grid_spacings = [15] * len(torsion_atom_indices)
    initial_molecules = torsion_data["initial_molecules"]
#    print(i, canonical_torsion_index, len(initial_molecules))

    # Check connectivity
    molecule = qcel.models.Molecule(**initial_molecules[0])
    conn = qcel.molutil.guess_connectivity(molecule.symbols, molecule.geometry)
    assert (len(conn) + 3) > len(molecule.symbols), conn

    try:
        ds.add_entry(
            canonical_torsion_index,
            initial_molecules,
            torsion_atom_indices,
            grid_spacings,
            energy_upper_limit=0.05,
            attributes=attributes,
            save=False,
        )
        i += 1
    except KeyError:
        continue

    # Save every 30 for speed
    if (i % 30) == 0:
        ds.save()

ds.save()
print("Submitting tasks...")
comp = ds.compute("default", tag="openff")
print(comp)

print("Complete!")