# Copyright (c) 2024, EleutherAI
# This file is based on code by the authors denoted below and has been modified from its original version.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os
from abc import ABC, abstractmethod
from multiprocessing import cpu_count
from datasets import load_dataset
from tqdm import tqdm
import zipfile

"""
This registry is for automatically downloading and extracting datasets.

To register a class you need to inherit the DataDownloader class, and provide name and url attributes, and (optionally)
the number of documents.

When done, add it to the DATA_DOWNLOADERS dict. The function process_data runs the pre-processing for the selected
dataset.
"""

GPT2_VOCAB_URL = "https://huggingface.co/datasets/RaviChandera/gpt2-vocab/raw/main/gpt2-vocab.json"
GPT2_MERGE_URL = "https://huggingface.co/datasets/RaviChandera/gpt2-merges/raw/main/gpt2-merges.txt"


class DataDownloader(ABC):
    """Dataset registry class to automatically download / extract datasets"""

    def __init__(
        self,
        tokenizer_type=None,
        merge_file=None,
        vocab_file=None,
        data_dir=None,
        force_redownload=None,
        num_workers=None,
        dataset_name=None,
    ):
        if tokenizer_type is None:
            tokenizer_type = "GPT2BPETokenizer"
        if data_dir is None:
            data_dir = os.environ.get("DATA_DIR", "./data")
        if merge_file is None:
            merge_file = f"{data_dir}/gpt2-merges.txt"
        if force_redownload is None:
            force_redownload = False
        if vocab_file is None:
            if tokenizer_type == "GPT2BPETokenizer":
                vocab_file = f"{data_dir}/gpt2-vocab.json"
            elif tokenizer_type == "HFGPT2Tokenizer":
                vocab_file = "gpt2"
            elif tokenizer_type == "CharLevelTokenizer":
                pass
            else:
                assert vocab_file is not None, "No vocab file provided"
        if num_workers is None:
            num_workers = cpu_count()
        self._tokenizer_type = tokenizer_type
        self._merge_file = merge_file
        self._vocab_file = vocab_file
        self._data_dir = data_dir
        self._force_redownload = force_redownload
        self._num_workers = num_workers
        self.dataset_name = dataset_name

    @property
    def base_dir(self):
        """base data directory"""
        return self._data_dir

    @property
    @abstractmethod
    def name(self):
        """name of dataset"""
        pass

    @property
    @abstractmethod
    def urls(self):
        """URLs from which to download dataset"""
        pass

    @property
    def tokenizer_type(self):
        """tokenizer type to use when tokenizing data"""
        return self._tokenizer_type

    @property
    def merge_file(self):
        """Merge file for tokenizer"""
        return self._merge_file

    @property
    def vocab_file(self):
        """Vocab file for tokenizer"""
        return self._vocab_file

    @property
    def num_workers(self):
        """Number of workers to use in preprocessing"""
        return self._num_workers

    @property
    def num_docs(self):
        """Number of documents in the dataset (if known)"""
        return None

    @property
    def ftfy(self):
        """Use ftfy (https://github.com/LuminosoInsight/python-ftfy) to fix text encodings"""
        return False

    def exists(self):
        """Checks if the dataset is present"""
        return os.path.isdir(f"{self.base_dir}/{self.name}")

    def download(self):
        """downloads dataset"""
        os.makedirs(os.path.join(self.base_dir, self.name), exist_ok=True)
        for url in self.urls:
            try:
                os_cmd = f"wget {url} -O {os.path.join(self.base_dir, self.name, os.path.basename(url))}"
                if os.system(os_cmd) != 0:
                    raise Exception(
                        f"Cannot download file at URL {url}: server may be down"
                    )
            except Exception as e:
                raise Exception(f"Download error: {e}")

    def tokenize(self, jsonl_filepath = None):

        """tokenizes dataset"""
        parent_folder = os.path.join(self.base_dir, self.name)
        jsonl_filepath = jsonl_filepath if jsonl_filepath is not None else ",".join(
            [os.path.join(parent_folder, os.path.basename(url)) for url in self.urls]
        )  

        cmd = f"python tools/datasets/preprocess_data.py \
            --input {jsonl_filepath} \
            --output-prefix {parent_folder}/{self.name} \
            --vocab {self.vocab_file} \
            --dataset-impl mmap \
            --tokenizer-type {self.tokenizer_type} \
            --merge-file {self.merge_file} \
            --append-eod \
            --workers {self.num_workers} "

        if self.num_docs is not None:
            cmd += f"--num-docs {self.num_docs} "

        if self.ftfy:
            cmd += f"--ftfy "

        os.system(cmd)

        
    def customdataset_from_text(self):

        os.makedirs(os.path.join(self.base_dir, self.name), exist_ok=True)
        download_dir = os.path.join(self.base_dir, self.name)

        zip_file_path = "/content/gpt-neox/data/text_file.zip"
        txt_files = [f for f in os.listdir(self.base_dir) if f.endswith('.txt') and f != "gpt2-merges.txt"]

        # Assert that there are .txt files
        assert txt_files, f"No textfile found at {self.base_dir}."
        
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:

            for txt_file in txt_files:
                file_path = os.path.join(self.base_dir, txt_file)
                zipf.write(file_path, os.path.basename(file_path))
                


    def prepare(self):
        
        if self.name == "customdataset":
            self.customdataset_from_text()
            zip_file_path = os.path.join(os.path.join(self.base_dir, self.name), f"{self.name}.zip")
            self.tokenize(zip_file_path)

        elif self._force_redownload:
            self.download()
            self.tokenize()
        else:
            if not self.exists():
                self.download()
            self.tokenize()
        


class Enron(DataDownloader):
    name = "enron"
    urls = ["http://eaidata.bmk.sh/data/enron_emails.jsonl.zst"]
    num_docs = 517401


class PileSubset(DataDownloader):
    name = "pile_00"
    urls = ["https://the-eye.eu/public/AI/pile/train/00.jsonl.zst"]


class Pile(DataDownloader):
    name = "pile"
    urls = [
        f"https://the-eye.eu/public/AI/pile/train/{i:02}.jsonl.zst" for i in range(30)
    ]


class Github(DataDownloader):
    name = "github"
    urls = ["http://eaidata.bmk.sh/data/github_small.jsonl.zst"]


class ArXiv(DataDownloader):
    name = "arxiv"
    urls = [
        "https://the-eye.eu/public/AI/pile_preliminary_components/2020-09-08-arxiv-extracts-nofallback-until-2007-068.tar.gz"
    ]


class EuroParl(DataDownloader):
    name = "europarl"
    urls = [
        "https://the-eye.eu/public/AI/pile_preliminary_components/EuroParliamentProceedings_1996_2011.jsonl.zst"
    ]


class FreeLaw(DataDownloader):
    name = "freelaw"
    urls = [
        "https://the-eye.eu/public/AI/pile_preliminary_components/FreeLaw_Opinions.jsonl.zst"
    ]


class NiH(DataDownloader):
    name = "nih"
    urls = [
        "https://the-eye.eu/public/AI/pile_preliminary_components/NIH_ExPORTER_awarded_grant_text.jsonl.zst"
    ]


class PubMed(DataDownloader):
    name = "pubmed"
    urls = [
        "https://the-eye.eu/public/AI/pile_preliminary_components/PMC_extracts.tar.gz"
    ]


class Books1(DataDownloader):
    name = "books1"
    urls = ["https://the-eye.eu/public/AI/pile_preliminary_components/books1.tar.gz"]


class Books3(DataDownloader):
    name = "books3"
    urls = ["https://the-eye.eu/public/AI/pile_preliminary_components/books3.tar.gz"]


class HackerNews(DataDownloader):
    name = "hackernews"
    urls = ["https://the-eye.eu/public/AI/pile_preliminary_components/hn.tar.gz"]
    num_docs = 373000


class OpenWebText2(DataDownloader):
    name = "openwebtext2"
    urls = [
        "https://huggingface.co/datasets/segyges/OpenWebText2/resolve/main/openwebtext2.jsonl.zst.tar"
    ]
    num_docs = 17103000


class StackExchange(DataDownloader):
    name = "stackexchange"
    urls = [
        "https://the-eye.eu/public/AI/pile_preliminary_components/stackexchange_dataset.tar"
    ]


class UbuntuIRC(DataDownloader):
    name = "ubuntu_irc"
    urls = [
        "https://the-eye.eu/public/AI/pile_preliminary_components/ubuntu_irc_until_2020_9_1.jsonl.zst"
    ]


class YoutubeSubtitles(DataDownloader):
    name = "youtube_subtitles"
    urls = [
        "https://the-eye.eu/public/AI/pile_preliminary_components/yt_subs.jsonl.zst"
    ]


class C4(DataDownloader):
    name = "c4"
    urls = [
        f"https://the-eye.eu/eleuther_staging/c4/en/c4-train.{i:05}-of-01024.json.gz"
        for i in range(1024)
    ]


class C4OpenWebText(DataDownloader):
    name = "c4_openwebtext"
    urls = [
        f"https://the-eye.eu/eleuther_staging/c4/realnewslike/c4-train.{i:05}-of-00512.json.gz"
        for i in range(512)
    ]


class CustomDataset(DataDownloader):
    name = "customdataset"
    urls = None 



def maybe_download_gpt2_tokenizer_data(tokenizer_type, data_dir):
    if tokenizer_type is None or tokenizer_type == "GPT2BPETokenizer":
        GPT2_VOCAB_FP = f"{data_dir}//gpt2-vocab.json"
        GPT2_MERGE_FP = f"{data_dir}/gpt2-merges.txt"
        if not os.path.isfile(GPT2_VOCAB_FP):
            os.system(f"wget {GPT2_VOCAB_URL} -O {GPT2_VOCAB_FP}")
        if not os.path.isfile(GPT2_MERGE_FP):
            os.system(f"wget {GPT2_MERGE_URL} -O {GPT2_MERGE_FP}")


DATA_DOWNLOADERS = {
    "pass": "pass",
    "enron": Enron,
    "pile_subset": PileSubset,
    "pile": Pile,
    "github": Github,
    "arxiv": ArXiv,
    "europarl": EuroParl,
    "freelaw": FreeLaw,
    "nih": NiH,
    "pubmed": PubMed,
    "books1": Books1,
    "books3": Books3,
    "hackernews": HackerNews,
    "openwebtext2": OpenWebText2,
    "stackexchange": StackExchange,
    "ubuntu_irc": UbuntuIRC,
    "youtube_subtitles": YoutubeSubtitles,
    "c4": C4,
    "c4_openwebtext": C4OpenWebText,
    "customdataset":CustomDataset,
}


def prepare_dataset(
    dataset_name: str,
    tokenizer_type: str = None,
    data_dir: str = None,
    vocab_file: str = None,
    merge_file: str = None,
    force_redownload: bool = None,
    num_workers: int = None,
):
    """
    Downloads + tokenizes a dataset in the registry (dataset_name) and saves output .npy files to data_dir.
    """
    if data_dir is None:
        data_dir = os.environ.get("DATA_DIR", "./data")
    os.makedirs(data_dir, exist_ok=True)
    maybe_download_gpt2_tokenizer_data(tokenizer_type, data_dir)
    DownloaderClass = DATA_DOWNLOADERS.get(dataset_name.split('/')[0].lower(), None)

    # print(f'check {dataset_name.split('/')[0]}')
    if DownloaderClass is None:
        raise NotImplementedError(
            f'Dataset "{dataset_name}" not recognized - please choose from {list(DATA_DOWNLOADERS.keys())}'
        )
    elif DownloaderClass == "pass":
        # pass on building dataset (for unit tests)
        pass

    else:
        num_workers = 1
        ds_name  = dataset_name if dataset_name.split('/')[0] in ["customdataset"] else None
        d = DownloaderClass(
            tokenizer_type=tokenizer_type,
            vocab_file=vocab_file,
            merge_file=merge_file,
            data_dir=data_dir,
            force_redownload=force_redownload,
            num_workers=num_workers,
            dataset_name = ds_name
        )
        d.prepare()
