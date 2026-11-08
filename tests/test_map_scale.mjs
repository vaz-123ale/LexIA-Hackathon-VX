import test from 'node:test';
import assert from 'node:assert/strict';
import {mapScale} from '../web/js/map.js';
test('escala cartografica diminui a distancia ao aproximar e conserva largura legivel',()=>{
 const bounds=[-82,-57,-32,13];
 const full=mapScale([25,92,690,433],810,bounds,600);
 const zoom=mapScale([100,150,345,216],810,bounds,600);
 assert.ok(full.distance>zoom.distance);
 for(const value of [full,zoom])assert.ok(Number.isFinite(value.width)&&value.width>0&&value.width<=170);
});
