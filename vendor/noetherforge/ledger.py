"""Persist exact claims, failed proposals and checked dependency edges."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime,timezone
from pathlib import Path

from .goals import digest
from .proofcheck import verify


class ClaimLedger:
    def __init__(self,path):
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('CREATE TABLE IF NOT EXISTS claims(id TEXT PRIMARY KEY,kind TEXT,certificate TEXT,evidence TEXT,seen INTEGER NOT NULL,created TEXT); CREATE TABLE IF NOT EXISTS edges(child TEXT REFERENCES claims(id),parent TEXT REFERENCES claims(id),mechanism TEXT,PRIMARY KEY(child,parent)); CREATE TABLE IF NOT EXISTS failures(id INTEGER PRIMARY KEY,proposal TEXT,evidence TEXT,created TEXT);')
        self.db.commit()
        if self.db.execute('PRAGMA user_version').fetchone()[0]<2:
            # The first prototype stored composite certificates but no embedded
            # piece edges. Reverify those certificates during this one-time upgrade.
            old=[json.loads(raw) for raw, in self.db.execute('SELECT certificate FROM claims')]
            for certificate in old: self.accept(certificate)
            self.db.execute("UPDATE edges SET mechanism='checked_certificate_dependency'")
            self.db.execute('PRAGMA user_version=2'); self.db.commit()

    def accept(self,certificate):
        evidence=verify(certificate)
        if not evidence['status'].startswith('CERTIFIED_'):
            self.reject(certificate,evidence)
            return {'status':'NOT_CERTIFIED','verification':evidence}
        key=digest(certificate)
        prior=self.db.execute('SELECT evidence FROM claims WHERE id=?',(key,)).fetchone()
        if prior and json.loads(prior[0])!=evidence:
            raise ValueError('A stored certificate has conflicting verification evidence')
        parent_certs=self.parents(certificate)
        parent_ids=[]
        for parent in parent_certs:
            result=self.accept(parent)
            if result['status']=='NOT_CERTIFIED': raise ValueError('Unchecked derivation parent')
            parent_ids.append(result['id'])
        now=datetime.now(timezone.utc).isoformat()
        self.db.execute('INSERT INTO claims VALUES(?,?,?,?,1,?) ON CONFLICT(id) DO UPDATE SET seen=seen+1',(key,certificate['kind'],json.dumps(certificate,sort_keys=True),json.dumps(evidence,sort_keys=True),now))
        for parent in parent_ids:
            if parent==key: raise ValueError('Circular claim dependency')
            self.db.execute('INSERT OR IGNORE INTO edges VALUES(?,?,?)',(key,parent,'checked_certificate_dependency'))
        self.db.commit()
        return {'id':key,'status':'PREVIOUSLY_VERIFIED' if prior else 'NEW_VERIFIED_CLAIM','verification':evidence,'parents':parent_ids,'historical_novelty':'UNREVIEWED'}

    def reject(self,proposal,evidence):
        self.db.execute('INSERT INTO failures(proposal,evidence,created) VALUES(?,?,?)',(json.dumps(proposal,sort_keys=True),json.dumps(evidence,sort_keys=True),datetime.now(timezone.utc).isoformat()))
        self.db.commit()

    def recheck(self):
        records=self.db.execute('SELECT id,certificate,evidence FROM claims ORDER BY id').fetchall()
        for key,raw,saved in records:
            certificate=json.loads(raw)
            if digest(certificate)!=key or verify(certificate)!=json.loads(saved):
                raise ValueError('A stored proof has changed or no longer verifies')
            expected={digest(p) for p in self.parents(certificate)}
            edges=self.db.execute('SELECT parent,mechanism FROM edges WHERE child=?',(key,)).fetchall()
            if {parent for parent,_ in edges}!=expected or any(mechanism!='checked_certificate_dependency' for _,mechanism in edges):
                raise ValueError('Stored dependency edges do not match the checked derivation')
        return {'status':'LEDGER_RECHECKED','verified_claims':len(records),'dependency_edges':self.db.execute('SELECT count(*) FROM edges').fetchone()[0],'failed_proposals':self.db.execute('SELECT count(*) FROM failures').fetchone()[0]}

    def close(self): self.db.close()

    @staticmethod
    def parents(certificate):
        if certificate.get('kind')=='algebraic_consequence': return certificate.get('parents',[])
        if certificate.get('kind')=='sharp_inequality_atlas': return [p['certificate'] for p in certificate['pieces']]
        return []

    def polynomial_generators(self,map_hash):
        result=[]
        for raw, in self.db.execute("SELECT certificate FROM claims WHERE kind='polynomial_invariant' ORDER BY id"):
            cert=json.loads(raw)
            if cert['map_hash']==map_hash:
                if not verify(cert)['status'].startswith('CERTIFIED_'): raise ValueError('A stored generator became invalid')
                result.append(cert)
        result.sort(key=lambda c:max(sum(t['powers']) for t in c['candidate']))
        return result[:16]

    def export(self):
        self.recheck()
        return {'schema_version':2,'claims':[{'id':i,'kind':k,'certificate':json.loads(c),'verification':json.loads(e),'seen':s,'created':t} for i,k,c,e,s,t in self.db.execute('SELECT * FROM claims ORDER BY id')],'edges':[{'child':c,'parent':p,'mechanism':m} for c,p,m in self.db.execute('SELECT * FROM edges ORDER BY child,parent')],'failed_proposals':[{'proposal':json.loads(p),'evidence':json.loads(e),'created':t} for _,p,e,t in self.db.execute('SELECT * FROM failures ORDER BY id')]}

    def import_snapshot(self,snapshot):
        if snapshot.get('schema_version')!=2: raise ValueError('Unsupported ledger snapshot')
        # Recheck all proofs before restoring any durable state.
        for row in snapshot['claims']:
            if digest(row['certificate'])!=row['id'] or verify(row['certificate'])!=row['verification']:
                raise ValueError('Snapshot proof or hash is invalid')
        for row in snapshot['claims']: self.accept(row['certificate'])
        for row in snapshot.get('failed_proposals',[]): self.reject(row['proposal'],row['evidence'])
        return self.recheck()
