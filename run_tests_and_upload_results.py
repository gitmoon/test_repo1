import sys, getopt
import subprocess
from subprocess import Popen, PIPE
from datetime import datetime


def subprocess_cmd(command: str):
    process = subprocess.Popen(command,stdout=sys.stdout)
    proc_stdout = process.communicate()
    print (proc_stdout)

def main(argv):
    global inputfile
    inputfile = ''
    try:
       opts, args = getopt.getopt(argv,"hi:o:",["ifile="])
    except getopt.GetoptError:
       print ('run_tests_and_upload_results.py -i <inputfiles> ')
       s = input('--> ')  
       sys.exit(2)
    for opt, arg in opts:
       if opt == '-h':
          print('Example :')
          print('python .\\run_tests_and_upload_results.py -i \'python -m pytest ./tests/test_dram.py  -v --junitxml=\"./test_results/result.xml\"\'')
          sys.exit()
       elif opt in ("-i", "--ifile"):
          inputfile = arg
          print(inputfile)
          
          
if __name__ == "__main__":
    main(sys.argv[1:])
    subprocess_cmd(inputfile)
    cur_time = "--description " + '\"'+ datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '\"'
    print(cur_time)
    args = f"\
    az artifacts universal publish \
    --organization https://dev.azure.com/jblprd/ \
    --project=\"Welbilt Software\" \
    --scope project \
    --feed welbilt-test-result \
    --name common_ui_result \
    --version 0.0.15 \
    {cur_time} \
    --path \"./test_results\" \
    "

    bckp = Popen(args, shell=True , stdout=subprocess.PIPE)
    text = bckp.stdout.read().decode("ascii") 
    print(text)


