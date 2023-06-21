## dev version
## assigning reads to whitelist
from fast_edit_distance import edit_distance
import multiprocessing as mp
import tempfile
import pandas as pd
import numpy as np
import swifter
import gzip
from Bio import SeqIO
import os

import blaze #read_batch_generator
import helper


def match_bc(bc, whitelist, max_ed):
    """_summary_
    Args:
        bc (str): putative bc to be assigned
        whitelist (list): list of bc to assign to
        max_ed (int): maximum edit distance allowed for a assignment
    Returns:
        assigned barcode <str>:  if a unambiguous barcode was found in the whitelist
        '': if no barcode was found in the whitelist
        'ambiguous': if multiple barcode was found in the whitelist
    """
    if not isinstance(bc, str): #nan
        return ''
    best_ed = max_ed
    bc_hit = ''
    for i in whitelist:
        ed = edit_distance(bc, i, best_ed) 
        if ed == 0:
            return i
        elif ed < best_ed:
            best_ed = ed
            bc_hit = i
        elif ed == best_ed:
            if not bc_hit:
                bc_hit = i
            else: 
                bc_hit = 'ambiguous'
                best_ed -= 1
                if best_ed < 0:
                    return ''
    return bc_hit
            
# Function to modify the header
def fastq_modify_header(record, barcode, UMI):
    record.id = f"{barcode}_{UMI}#{record.id}"
    record.description = ""
    return record

def fastq_trim_seq(record, start = 0, end = None):
    """trim reads using 0-based index
    note end can be either positive or negative, following python idexing rules
    """
    if not end:
        
        qscore = \
            record.letter_annotations['phred_quality'][start:]
        record.letter_annotations = {}
        record.seq = record.seq[start:]
        record.letter_annotations['phred_quality']=qscore
    else:
        qscore = \
            record.letter_annotations['phred_quality'][start:end]
        record.letter_annotations = {}
        record.seq = record.seq[start:end]
        record.letter_annotations['phred_quality']=qscore
    return record

def batch_barcode_to_fastq(read_batch, mapping_df ,gz = True):
    """Take a read batch, write fastq/fastq.gz to a tmp file
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file_path = temp_file.name
    output_handle = gzip.open(temp_file_path, 'wt') if gz else open(temp_file_path, 'w')
    records = []
    for r in read_batch:
        row = mapping_df.loc[r.id] #the row in putative bc table
        if row.putative_bc == np.nan:
            continue
        r = fastq_modify_header(r, row.BC_corrected, row.putative_umi)
        if row.umi_end < 0:
            r = fastq_trim_seq(r,end = row.umi_end)
        else:
            r = fastq_trim_seq(r,start = row.umi_end)
        records.append(r)
    SeqIO.write(records, output_handle, "fastq")
    output_handle.close()

def assign_barcodes(putative_bc_csv, whitelsit_csv, n_process):
    # read putative barcode
    df = pd.read_csv(putative_bc_csv)
    
    # read whitelist
    whitelist = [] 
    with open(whitelsit_csv, 'r') as f:
        for line in f:
            whitelist.append(line.split('-')[0])

    df['BC_corrected'] =\
      df['putative_bc'].\
        swifter.allow_dask_on_strings(enable=True).\
            set_dask_scheduler('processes').\
                set_npartitions(n_process).\
                    apply(match_bc, whitelist=whitelist, max_ed=2)
    
    #df = df.set_index('read_id')# need UMI
    return df
    


# def main(fastq_ins, fastq_out, putative_bc_csv, whitelsit_csv, n_process, gzip):
#     assignment_df = assign_barcodes(putative_bc_csv, whitelsit_csv, n_process)
#     r_batch = blaze.read_batch_generator(fastq_ins, batch_size=50)
#     rst_futures = helper.multiprocessing_submit(batch_barcode_to_fastq, 
#                            r_batch, 
#                            n_process=n_process,
#                              mapping_df = assignment_df
#                              ,gzip = gzip)
 
#     while next(rst_futures, None):
#         pass # wait until all job finished
    
def main(fastq_fns, fastq_out, putative_bc_csv, whitelsit_csv, n_process, gz, batchsize):
    # check file exist. Avoid overwrite
    i = 1
    while os.path.exists(fastq_out):
        fastq_out = f'{fastq_out.split("_")[0]}_{i}'
        i+=1

    output_handle = gzip.open(fastq_out, 'wt') if gz else open(fastq_out, 'w')
    assignment_df = assign_barcodes(putative_bc_csv, whitelsit_csv, n_process)
    

    r_batches = blaze.read_batch_generator(fastq_fns, batchsize)
    
    read_idx = 0
    for read_batch in r_batches:
        records = []
        for r in read_batch:
            row = assignment_df.iloc[read_idx]#the row in putative bc table
            read_idx += 1 
            if row.read_id != r.id:
                print(row.read_id, r.id)
            if row.putative_bc is np.nan:
                continue
            r = fastq_modify_header(r, row.BC_corrected, row.putative_umi)
            if row.umi_end < 0:
                r = fastq_trim_seq(r,end = int(row.umi_end))
            else:
                r = fastq_trim_seq(r,start = int(row.umi_end))
            records.append(r)
        SeqIO.write(records, output_handle, "fastq")
    output_handle.close()

if __name__ == '__main__':
    main()