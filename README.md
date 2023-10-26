<img src="logo.png" width="300"/>

# BLAZE (Barcode identification from Long reads for AnalyZing single cell gene Expression)
[![](https://img.shields.io/pypi/v/blaze2)](https://pypi.org/project/blaze2/)
![Github All Releases](https://img.shields.io/github/downloads/shimlab/BLAZE/total?label=Github%20download)
![PyPI - License](https://img.shields.io/pypi/l/blaze2)
![PyPI - Downloads](https://img.shields.io/pypi/dm/blaze2?label=PyPI%20Downloads)


**Important Notes:** This repo is actively being updated. Please make sure you have the latest release.

## Keywords:
Oxford Nanopore sequencing, Demultiplexing, Single Cell, Barcode.

# Overview
Combining single-cell RNA sequencing with Nanopore long-read sequencing enables isoform level analysis in single cells. However, due to the relatively high error rate in Nanopore reads, the demultiplexing of cell barcodes and Unique molecular Identifiers (UMIs) is challenging. This tool enables the accurate identification of barcodes solely from Nanopore reads. The output of BLAZE is a barcode whitelist that can be utilised by downstream tools such as FLAMES to quantify genes and isoforms in single cells. For a detailed description of how BLAZE works and its performance across different datasets, please see our [Genome Biology paper](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-023-02907-y).

# Version 2.x Update vs. Version 1.x
* Significant runtime improvement
* Add more information into the putative barcode table:
    * putative UMI
    * UMI end position (used for later trimming the adator-UMI sequence from each reads)
    * Flanking bases before barcode and after UMI (for correction of insertion and deletion within the putative barcode and UMIs)
* Add a final step to perform read-to-whitelist assignment. A putative barcode (16nt) with first be extended to include flanking bases from both sides. Then we scan though the whitelist and find the one with lowest subsequence ED (defined as the minimum edits required to make a shorter sequence a subsequence of the longer on). The UMI position will also be corrested if some insertion and deletion found within the 16nt putative barcode.
* The bases before and included in UMI will be trimmed it the demultiplexed reads. The output format will be in fastq or fastq.gz. The header with be `@<16 nt BC>_<12 nt UMI>#read_id_<strand>`
* `--emptydrop` option in v1.x is on by default and is no longer user-specified.

# Installation
`pip3 install blaze2`

## <a name="dependencies"></a>Dependencies
* `Biopython`
* `pandas`
* `numpy`
* `tqdm`
* `matplotlib`
* `fast-edit-distance`

# Running BLAZE

## **Required Input:** 
 * **Long-read fastq files**
 * **Expected number of cells**: The expected number of cells is a required input (specified by `--expect-cells=xx`). Note that the output is robust to the specified number, but a rough number is needed to determine the count threshold to output the barcode list. 
* **10X barcode whitelist**: a file containing all possible 10x barcodes ([more details](https://kb.10xgenomics.com/hc/en-us/articles/115004506263-What-is-a-barcode-whitelist-)). Note that there is no need to specify the file if you are using 10 Single Cell 3' gene expression v2 or v3 chemistry. The corresponding whitelists already been packed. By default BLAZE will assume it's 
v3 chemistry and automatically choose the corresponding 10X whitelist. You may specify `--kit-version=v2` if the data were generated by the v2 chemistry. You may also provide your own whitelist by specifying `--full-white-list=<filename>` (e.g., you used customised barcodes).

## Running BLAZE:

Running whole pipline:
```
blaze --expect-cells <int> --output-prefix <prefix> --threads <int>  <path to the fastq(s)>
```
The details of the pipeline and output can be found [here](#Understanding-the-BLAZE-pipeline-and-output). Please run `blaze -h` for more options.

## Understanding the BLAZE pipeline and output 
BLAZE performs the following steps:

**Step 1: locating the putative barcodes and UMI sequence in each read:**

BLAZE first searches for the putative barcodes (i.e. barcode in read without error correction) by locating 10X adapter and polyT in the reads. Both the sequenced strand and reverse complement strand are considered for each read. These putative barcodes and their quality scores (minQ) are recorded in `putative_bc.csv`. The IDs of reads where no putative barcode can be located are also listed in the file but without any putative barcode or minQ score.
* Output 1. Putative barcode in each read, default filename: `putative_bc.csv`. It contains 3 columns:
        
    * col1: read id
    * col2: putative barcode (i.e. the basecalled barcode segment in each read, specifically the 16nt sequence after the identifed 10X adaptor within each read **without correction for any basecalling errors**)
    * col3: minimum Phred score of the bases in the putative barcode
    * col4: putative_umi
    * col5: 0-based UMI end position in each read, a positive value indicates that the barcode and UMI were found at forward strand the read, and a negative value indicates the barcode and UMI were extracted (including the flanking sequencing in col 6 & 7) from the reverse strand.
    * col6: flanking sequence immediately upstream to the barcode in the reads
    * col7: flanking sequence immediately downstream to the UMI in the reads

    **Note:** col 2 to 7 will be empty if no barcode is found within a read. 

**Step 2: generating the barcode list.**
To accurately identify the barcode list, BLAZE first identifies **high-quality** putative barcodes by choosing putative barcodes that exactly match the 10X barcode whitelist and have minQ >= threahold (Default: 15). Next, BLAZE scans through the list of high-quality putative barcodes and counts the number of appearances of each unique barcode sequence.  
Finally, BLAZE generates cell-associated barcode list by picking unique barcodes whose counts are above a quantile-based threshold; In addition, BLAZE picks those unique barcodes that likely associated with empty droplet by choosing unique barcodes that are at least certain edit distance (Default: 5) from the cell-associated barcodes list. The empty-droplet-associated barcodes can be use for estimating the embient RNA expression.

* Output 2: Cell-ranger style cell-associated barcode list, default filename: `whitelist.csv`.
* Output 3: "Barcode rank plot"" (or "knee plot") using the high-quality putative barcodes.
* Output 4: list of barcodes associated with empty droplets, default filename: `emtpy_bc.csv`.

**Step 3: assigning reads to the barcodes.**
With the barcode list generated in step 2, BLAZE assigns reads to the cells by comparing the putative barcodes with the barcode list and finding the closest match. Specifically, for each read, the putative barcode has been identified in step 1. Among the barcode list, BLAZE identifies the barcode with lowest ED from the read. Note that the reads would not be assigned if 1. the lowest ED is larger that a threshold (Default: 2). 2. Multiple barcodes in the list have the lowest ED.

* Output 5: fastq files with modified read name: @\<barcode>\_\<UMI>\_\<original read id>_<strand ('+' or '-')>. For strand, '+' means the the barcode identified from the forward strand of the read and '-' means the reverse strand. 

Note: the output fastq can be directly use in [FLAMES](https://github.com/OliverVoogd/FLAMES) for downstream steps.

## Additional (optional) features

### High-sensitivity mode
By default, BLAZE is configured to minimise false-positive barcode detections and is therefore relatively conservative. BLAZE has a high-sensitivity mode for users who prioritise high recall of the barcodes (and cells) present. To use specify `--high-sensitivity-mode`. Users should be aware that high-sensitivity mode trades higher recall (i.e. more true barcodes) for potentially lower precision (i.e. more non-cell associated barcodes) and therefore we recommended running an empty drops analysis[[1]](#1) to distinguish cell-associated barcodes and barcodes from empty droplets with an ambient RNA expression profile.

## **Example code:**

Run BLAZE in default mode: the expected number of cells are set to be 1000 and run with 12 threads
```
blaze --expect-cells=1000 --threads=12 path/to/fastq_pass
```
Run BLAZE in high-sensitivity mode: the expected number of cells are set to be 1000 and run with 12 threads
```
blaze --high-sensitivity-mode --expect-cells=1000 --threads=12 path/to/fastq_pass
```

## Rerun blaze or update previous run(s)
By default, BLAZE reuses the existing files if exist. For example, if you need to change some settings and rerun blaze after running  

```
blaze --expect-cells 500 --output-prefix ourdir/ --threads 8  /data
```

, you will need to specify a different prefix or specify `--overwrite`. Otherwise, the output would NOT be updated. 

BLAZE runs the [3 steps above](#Understanding-the-BLAZE-pipeline-and-output) sequentially, if you believe some file in the previous run can be reused, you could keep them to skip corresponding steps. For example, you have run the following code, which generated the output from he 1st and 2nd steps:

```
blaze --expect-cells 500 --output-prefix ourdir/ --no-demultiplexing --threads 8  /data
```
Afterwards, if you need the demultiplexing result, you can direct run
```
blaze --expect-cells 500 --output-prefix ourdir/ --threads 8  /data
```
and BLAZE will skip the 1st and 2nd steps as the output files were found in `outdir/`, which is much faster than rerunning the entire pipeline. However, if runtime is not a concern, it's recommanded to use `--overwrite` option which always run from the beginning and update all the output files. 


**More information:**
```
blaze -h
```




# Limitation:
BLAZE has been tested on Chromium **Single Cell 3ʹ gene expression v3** and should also work on **Chromium Single Cell 3ʹ gene expression v2**. However, it doesn't yet support any 10X 5' gene expression kits.

# Citing BLAZE

If you find BLAZE useful for your work, please cite our paper:

>You, Y., Prawer, Y. D., De Paoli-Iseppi, R., Hunt, C. P., Parish, C. L., Shim, H., & Clark, M. B. (2023) Identification of cell barcodes from long-read single-cell RNA-seq with BLAZE. Genome Biol 24, 66.
>[You et al. 2023](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-023-02907-y)


# Data availability
The data underlying the article "Identification of cell barcodes from long-read single-cell RNA-seq with BLAZE" are available from ENA under accession PRJEB54718. The processed data and scripts used in this study are available at https://github.com/youyupei/bc_whitelist_analysis/.


# References
<a id="1">[1]</a> 
Lun, A. T., Riesenfeld, S., Andrews, T., Gomes, T., & Marioni, J. C. (2019). EmptyDrops: distinguishing cells from empty droplets in droplet-based single-cell RNA sequencing data. Genome biology, 20(1), 1-9.

## Test run
The following command runs BLAZE on a test dataset provided in `/test/data`. The expected output can be found [here](test/).
```
bash test/run_test.sh
```
