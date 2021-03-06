#!/usr/bin/env python
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Find header files missing in GN.

This script gets all the header files from ninja_deps, which is from the true
dependency generated by the compiler, and report if they don't exist in GN.
"""

import argparse
import json
import os
import re
import subprocess
import sys


def GetHeadersFromNinja(out_dir):
  """Return all the header files from ninja_deps"""
  ninja_out = subprocess.check_output(['ninja', '-C', out_dir, '-t', 'deps'])
  return ParseNinjaDepsOutput(ninja_out)


def ParseNinjaDepsOutput(ninja_out):
  """Parse ninja output and get the header files"""
  all_headers = set()

  prefix = '..' + os.sep + '..' + os.sep

  is_valid = False
  for line in ninja_out.split('\n'):
    if line.startswith('    '):
      if not is_valid:
        continue
      if line.endswith('.h') or line.endswith('.hh'):
        f = line.strip()
        if f.startswith(prefix):
          f = f[6:]  # Remove the '../../' prefix
          # build/ only contains build-specific files like build_config.h
          # and buildflag.h, and system header files, so they should be
          # skipped.
          if not f.startswith('build'):
            all_headers.add(f)
    else:
      is_valid = line.endswith('(VALID)')

  return all_headers


def GetHeadersFromGN(out_dir):
  """Return all the header files from GN"""
  subprocess.check_call(['gn', 'gen', out_dir, '--ide=json', '-q'])
  gn_json = json.load(open(os.path.join(out_dir, 'project.json')))
  return ParseGNProjectJSON(gn_json)


def ParseGNProjectJSON(gn):
  """Parse GN output and get the header files"""
  all_headers = set()

  for _target, properties in gn['targets'].iteritems():
    for f in properties.get('sources', []):
      if f.endswith('.h') or f.endswith('.hh'):
        if f.startswith('//'):
          f = f[2:]  # Strip the '//' prefix.
          all_headers.add(f)

  return all_headers


def GetDepsPrefixes():
  """Return all the folders controlled by DEPS file"""
  gclient_out = subprocess.check_output(
      ['gclient', 'recurse', '--no-progress', '-j1',
       'python', '-c', 'import os;print os.environ["GCLIENT_DEP_PATH"]'])
  prefixes = set()
  for i in gclient_out.split('\n'):
    if i.startswith('src/'):
      i = i[4:]
      prefixes.add(i)
  return prefixes


def ParseWhiteList(whitelist):
  out = set()
  for line in whitelist.split('\n'):
    line = re.sub(r'#.*', '', line).strip()
    if line:
      out.add(line)
  return out


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--out-dir', default='out/Release')
  parser.add_argument('--json')
  parser.add_argument('--whitelist')
  parser.add_argument('args', nargs=argparse.REMAINDER)

  args, _extras = parser.parse_known_args()

  d = GetHeadersFromNinja(args.out_dir)
  gn = GetHeadersFromGN(args.out_dir)
  missing = d - gn

  deps = GetDepsPrefixes()
  missing = {m for m in missing if not any(m.startswith(d) for d in deps)}

  if args.whitelist:
    whitelist = ParseWhiteList(open(args.whitelist).read())
    missing -= whitelist

  missing = sorted(missing)

  if args.json:
    with open(args.json, 'w') as f:
      json.dump(missing, f)

  if len(missing) == 0:
    return 0

  print 'The following files should be included in gn files:'
  for i in missing:
    print i
  return 1


if __name__ == '__main__':
  sys.exit(main())
