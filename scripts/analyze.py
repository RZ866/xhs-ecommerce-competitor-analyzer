#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path
from xhs_analyzer.storage import SnapshotStore, read, dump, field_inventory
from xhs_analyzer.transport import TikHubClient, ProviderError, ENDPOINTS
from xhs_analyzer.providers import TikHubProvider, FixtureClient, identity, validate_contract
from xhs_analyzer.pipeline import collect
from xhs_analyzer.analysis import build_result, validate_ai
from xhs_analyzer.ai import write_request, remote_analysis
from xhs_analyzer.mock import fixture_analysis
from xhs_analyzer.report import render

ROOT = Path(__file__).resolve().parents[1]

def bounded(low, high):
    def check(value):
        n = int(value)
        if not low <= n <= high:
            raise argparse.ArgumentTypeError(f'must be {low}..{high}')
        return n
    return check

def main(argv=None):
    parser = argparse.ArgumentParser(description='Public XHS ecommerce research; no login/cookies')
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run')
    run.add_argument('url')
    run.add_argument('--provider', choices=['mock','tikhub'], default='tikhub')
    run.add_argument('--contract', type=Path)
    run.add_argument('--mode', choices=['boss','deep'], default='deep')
    run.add_argument('--notes-limit', type=bounded(1,100), default=100)
    run.add_argument('--deep-notes', type=bounded(1,100), default=20)
    run.add_argument('--comment-notes', type=bounded(0,100), default=10)
    run.add_argument('--comments-per-note', type=bounded(1,1000), default=100)
    run.add_argument('--out', type=Path, default=ROOT/'reports'/'latest')
    run.add_argument('--cache-dir', type=Path, default=ROOT/'data')
    run.add_argument('--cache-ttl', type=bounded(0,604800), default=86400)
    run.add_argument('--timeout', type=bounded(1,120), default=30)
    run.add_argument('--retries', type=bounded(0,3), default=2)
    run.add_argument('--interval', type=float, default=1)
    run.add_argument('--max-api-calls', type=bounded(1,1000), default=200)
    run.add_argument('--ai', choices=['agent','remote','mock'], default='agent')
    run.add_argument('--images', action='store_true', help='Fetch public XHS CDN covers without cookies')
    finalize = sub.add_parser('finalize')
    finalize.add_argument('--out', type=Path, required=True)
    finalize.add_argument('--analysis', type=Path)
    probe = sub.add_parser('probe', help='Capture one paid API response without guessing a response schema')
    probe.add_argument('url')
    probe.add_argument('--kind', choices=list(ENDPOINTS), default='account')
    probe.add_argument('--note-id')
    probe.add_argument('--out', type=Path, default=ROOT/'data')
    certify = sub.add_parser('validate-contract')
    certify.add_argument('--draft', type=Path, required=True)
    certify.add_argument('--snapshots', type=Path, required=True)
    certify.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'validate-contract':
            dump(args.out, validate_contract(read(args.draft), args.snapshots))
            print('Observed field contract validated:', args.out)
            return 0
        if args.command == 'probe':
            aid = identity(args.url)
            params = {'user_id': aid}
            if args.kind in ('comments', 'detail'):
                if not args.note_id or not __import__('re').fullmatch('[a-fA-F0-9]{24}', args.note_id):
                    raise ValueError('A validated 24-hex note ID from the notes response is required')
                params = {'note_id': args.note_id}
            if args.kind == 'products':
                params['page'] = 1
            payload, snapshot = TikHubClient(SnapshotStore(args.out), retries=0, max_calls=1).get(args.kind,params)
            dump(args.out/'inventory'/f'{args.kind}.json', {'snapshot':snapshot,'fields':field_inventory(payload),
                                                         'note':'Actual response structure only; inspect upstream success before mapping.'})
            print('Saved raw snapshot and field inventory:', args.out/'inventory'/f'{args.kind}.json')
            return 0
        if args.command == 'finalize':
            dataset = read(args.out/'dataset.json')
            ai = validate_ai(read(args.analysis or args.out/'analysis.json'), dataset)
            print('Report:', render(build_result(dataset, ai), args.out, dataset))
            return 0
        identity(args.url)
        if args.interval < .1 or not __import__('math').isfinite(args.interval):
            raise ValueError('interval must be finite and at least 0.1 seconds')
        synthetic = args.provider == 'mock'
        if args.ai == 'mock' and not synthetic:
            raise ValueError('Mock AI is forbidden for real data')
        if synthetic:
            fixtures = ROOT/'tests'/'fixtures'
            provider = TikHubProvider(FixtureClient(fixtures, SnapshotStore(args.cache_dir/'mock', args.cache_ttl, 'synthetic-fixture')),
                                      read(fixtures/'contract.json'), True)
        else:
            if not args.contract:
                raise ValueError('Live response fields are unverified. Run probe, inspect snapshots, validate a field contract, then pass --contract. See references/api-contract.md.')
            provider = TikHubProvider(TikHubClient(SnapshotStore(args.cache_dir, args.cache_ttl), args.timeout,args.retries,args.interval,
                                                  max_calls=args.max_api_calls), read(args.contract))
        dataset = collect(provider,args.url,args.out,args.notes_limit,args.deep_notes,args.comment_notes,args.comments_per_note,args.mode,args.images)
        write_request(dataset,args.out)
        ai, warning = None, None
        if synthetic:
            # A single mock command always yields a complete synthetic example.
            ai = fixture_analysis(dataset)
        elif args.ai == 'remote':
            try:
                ai = remote_analysis(dataset)
            except (ProviderError, ValueError, KeyError, TypeError):
                warning = '远程 AI 失败或证据校验未通过；保留数据和 Agent 分析交接文件。'
        if ai:
            dump(args.out/'analysis.json',ai)
        path = render(build_result(dataset,ai,warning),args.out,dataset)
        print('Report:',path)
        print('AI status:', 'complete (synthetic fixture)' if synthetic else ('complete' if ai else 'pending; see analysis-request.md'))
        return 0
    except (ValueError, ProviderError, OSError, KeyError, TypeError) as exc:
        from xhs_analyzer.storage import redact
        # Only our validation messages are emitted; do not echo raw OS/network error strings.
        print('Error:', redact(str(exc)) if isinstance(exc,(ValueError,ProviderError)) else type(exc).__name__, file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
