import os
import zipfile
from argparse import Namespace
import shutil

import pytest

from tests import TEST_DATA_ROOT, OUTPUT_FOLDER
from tests.temp_dir import TempDir, LocalTempDir
from tests.utils import _copy_between_filesystems
from vpt.filesystem import vzg_open, initialize_filesystem
from vpt.vizgen_postprocess import main


def get_arguments(temp_dir: TempDir):
    path = temp_dir.get_temp_path()
    sep = temp_dir.get_sep()

    args = Namespace(
        subparser_name='update-vzg',
        input_boundaries=sep.join([path, 'cells_cellpose.parquet']),
        input_vzg=sep.join([path, 'fake_vzg.vzg']),
        output_vzg=sep.join([path, 'test_vzg.vzg']),
        input_entity_by_gene=sep.join([path, 'cell_by_gene.csv']),
        input_metadata=None,
        temp_path=str(OUTPUT_FOLDER / 'temp'),
        z_count=1,
        processes=2,
        overwrite=True,
        profile_execution_time=None,
        verbose=False,
        log_level=1,
        log_file=None,
        aws_profile_name=None,
        aws_access_key=None,
        aws_secret_key=None,
        gcs_service_account_key=None,
        dask_address=None,
    )

    _copy_between_filesystems(str(TEST_DATA_ROOT / 'cells_cellpose.parquet'), args.input_boundaries)
    _copy_between_filesystems(str(TEST_DATA_ROOT / 'fake_vzg.vzg'), args.input_vzg)
    _copy_between_filesystems(str(TEST_DATA_ROOT / 'cell_by_gene.csv'), args.input_entity_by_gene)

    return args


def func_update_vzg(fakesNamespaceArgs):
    main(fakesNamespaceArgs)

    datasetPath = os.path.join(fakesNamespaceArgs.temp_path, 'fake_vzg')
    with vzg_open(fakesNamespaceArgs.output_vzg, 'rb') as f:
        with zipfile.ZipFile(f, 'r') as zip_ref:
            zip_ref.extractall(datasetPath)

    for lodType in ['max', 'min', 'middle']:
        cellsBinFilesList = os.listdir(os.path.join(datasetPath, 'cells_packed', lodType))
        assert len(cellsBinFilesList) == 7 + 2

    # deleting temporary file
    if os.path.exists(fakesNamespaceArgs.temp_path):
        shutil.rmtree(fakesNamespaceArgs.temp_path)

    if os.path.exists(fakesNamespaceArgs.output_vzg):
        os.remove(fakesNamespaceArgs.output_vzg)


@pytest.mark.parametrize('temp_dir', [LocalTempDir()], ids=str)
def test_func_local_update_vzg(temp_dir: TempDir):
    initialize_filesystem()
    try:
        args = get_arguments(temp_dir)
        func_update_vzg(args)
    finally:
        temp_dir.clear_dir()
