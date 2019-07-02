#!/usr/bin/env python

import copy
import json
from collections import Counter
import qcportal as ptl
from qcelemental.models import Molecule

def read_molecules(input_json):
    """ Extract the molecules and the index of them from the input json file

    Parameters
    ----------
    input_json: str,
        JSON file name to the output json of generate.py
        The data in the json file should be a list of {'initial_molecules': [..], 'cmiles_identifiers':{}}.

    Returns
    -------
    molecules_dict: dict
        The dictionary maps the index of a molecule to a Molecule object. e.g.
        {
            index1: Molecule1,
            index2: Molecule2,
        }

    molecule_attributes: dict
        The dicitonary maps the index of a molecule to the attributes of the molecule, e.g.
        {
            index1: {'canonical_explicit_hydrogen_smiles': .., 'canonical_isomeric_smiles': .., ..}
        }

    Note
    ----
    1. The mdata['cmiles_identifiers']['canonical_isomeric_smiles'] is selected as the index.
    2. For molecules have the same "canonical_isomeric_smiles", we use index-1, index-2 to distinguish them.
    """
    molecules_dict = {}
    molecule_attributes = {}
    with open(input_json) as infile:
        molecule_data_list = json.load(infile)
    index_counter = Counter()
    for mdata in molecule_data_list:
        initial_molecules = mdata['initial_molecules']
        cmiles_ids = mdata['cmiles_identifiers']
        index = cmiles_ids['canonical_isomeric_smiles']
        for i_conformer, initial_molecule in enumerate(initial_molecules):
            qcel_molecule = Molecule.from_data(initial_molecule)
            # use count to generate unique index
            index_count = index_counter[index]
            this_index = f'{index}-{index_count}'
            index_counter[index] += 1
            assert this_index not in molecules_dict, f"Multiple molecules have the same index, please check {mdata}"
            molecules_dict[this_index] = qcel_molecule
            molecule_attributes[this_index] = cmiles_ids
    return molecules_dict, molecule_attributes


def create_optimization_dataset(molecules_dict, client_config_file, dataset_name, qm_method, qm_basis, \
        spec_name='default', molecule_attributes={}, start_compute=False):
    """
    Submit a list of molecules for optimization

    Parameters
    ----------
    molecules_dict: dict {str: qcelemental.models.Molecule}
        The dictionary contains molecules to be submitted. The key is the index (name) of the molecule,
        value is a Molecule object.
    client_config_file: str
        File name for the QCPortal client configuration.
    dataset_name: str
        Name of the dataset to be created
    qm_method: str
        QM method to use for geometry optimization
    qm_basis: str
        QM basis set to use for geometry optimization
    spec_name: str
        The name of the QM spec, default is "default"
    start_compute: bool
        If true, start compute this dataset after creation
    molecule_attributes: dict {str: dict}
        The dictionary contains attributes for each molecule. The key is the index (name) of the molecule,
        value is a dictionary containing all the attributes for this molecule

    Returns
    -------
    ds: qcportal.collections.OptimizationDataset
        The dataset created

    """
    client = ptl.FractalClient.from_file(client_config_file)
    # create a new dataset with specified name
    print(f"Creating OptimizationDataset < {dataset_name} >")
    ds = ptl.collections.OptimizationDataset(dataset_name, client=client)
    # create specification for this dataset
    opt_spec = {"program": "geometric"}
    qc_spec = {"driver": "gradient", "method": qm_method, "basis": qm_basis, "program": "psi4"}
    ds.add_specification(spec_name, opt_spec, qc_spec)
    # add molecules
    print(f"Adding {len(molecules_dict)} molecules")
    for molecule_index, molecule in molecules_dict.items():
        attributes = molecule_attributes.get(molecule_index, {})
        ds.add_entry(molecule_index, molecule, attributes=attributes)
    # start compute
    if start_compute:
        ds.compute(spec_name)
    return ds


def main():
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("input_json", help="Input json file that contains a list of {initial_molecules,cmiles_identifiers}")
    parser.add_argument("dataset_name", help="Name of the OptimizationDataset to be created")
    parser.add_argument("client_config", help="Configuration file for creating the QCPortal.client")
    parser.add_argument("-m", "--qm_method", default='b3lyp-d3bj', help="QM method to use for optimization")
    parser.add_argument("-b", "--qm_basis", default='dzvp', help="QM basis to use for optimization")
    parser.add_argument("--start", action="store_true", help="Start compute for the created dataset")
    args = parser.parse_args()

    molecules_dict, molecule_attributes = read_molecules(args.input_json)

    create_optimization_dataset(molecules_dict, args.client_config, args.dataset_name, args.qm_method, args.qm_basis, \
        spec_name='default', molecule_attributes=molecule_attributes, start_compute=args.start)

if __name__ == "__main__":
    main()