#!/usr/bin/env node
// Agent-internal runtime discovery; no global installations or shell interpolation.
const fs=require('fs'),path=require('path'),os=require('os'),{spawnSync}=require('child_process');
const root=path.resolve(__dirname,'..');
const candidates=['python3','python','py',path.join(os.homedir(),'.cache','codex-runtimes','codex-primary-runtime','dependencies','python','python.exe')];
for(const exe of candidates){
  const check=spawnSync(exe,['-c','import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'],{timeout:15000,windowsHide:true});
  if(!check.error&&check.status===0){const run=spawnSync(exe,[path.join(root,'scripts','analyze.py'),...process.argv.slice(2)],{stdio:'inherit',windowsHide:true});process.exit(run.status??2);}
}
console.log('当前工具暂不具备运行此分析的条件，本次无法完成拆解。');process.exit(2);
