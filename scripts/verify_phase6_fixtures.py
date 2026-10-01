#!/usr/bin/env python3
"""Record all local fixture outcomes without exporting fixture/audit payloads."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tests',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--image-id',required=True)
    args=parser.parse_args()
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover(str(args.tests)))
    receipt={'verifiedAt':datetime.now(timezone.utc).isoformat(),'imageId':args.image_id,
             'testsRun':result.testsRun,'passed':result.wasSuccessful(),
             'failures':[test.id() for test,_ in result.failures],
             'errors':[test.id() for test,_ in result.errors],
             'skipped':[test.id() for test,_ in result.skipped]}
    args.output.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
