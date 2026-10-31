# SENSITIVITY — Holm family definition (A: adjacent ladder steps, as in diagnostics.md D3; B: ladder referenced to B_full)

Run: `python -B experiments/analysis/revision1_holm_bfull_family.py`.

Family A control: **PASS**. All 17 raw and adjusted p-values (χ² and exact), and all other row fields, exactly reproduce diagnostics.json; every displayed D3 table value reproduces diagnostics.md. The exact moderator permutation p is independently recomputed by enumerating all 2,704,156 label splits.

Each family contains 17 tests. Family B replaces only the five bundle comparisons; the other 12 hypotheses, pair sets, effects and raw p-values remain unchanged. Holm is recomputed separately for χ² p-values and exact p-values using the imported diagnostics function.

Bundles are not cumulative: B_noVolatile, B_noState and B_noSemantic each change B_full; B_identityCore and B_minimalCore are fixed sets (ladder_composition.md). Each B_full comparison uses the same 960 gpt-4.1 pairs across F0–F3, 24 pages × 10 tasks × 4 encodings.

The table is the union of the two families (21 distinct hypotheses). “—” means not in that family or not applicable; it is not a nonsignificant verdict. Δ = second − first; b = second-only successes, c = first-only. The significance column uses χ² Holm p < 0.05. Flags check both χ² and exact Holm verdicts on shared hypotheses. Replacement rows are marked A only / B only.

| comparison | Δ pp | b | c | χ² | p raw | p Holm (A) | p Holm (B) | p exact | p Holm exact (A) | p Holm exact (B) | significant at 0.05 after Holm: A / B | flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B_full → B_noVolatile | +9.48 | 102 | 11 | 73.28 | 1.12e-17 | 1.68e-16 | 1.68e-16 | 1.25e-19 | 1.88e-18 | 1.88e-18 | yes / yes | — |
| B_noVolatile → B_noState | -9.17 | 10 | 98 | 71.70 | 2.50e-17 | 3.50e-16 | — | 2.65e-19 | 3.71e-18 | — | yes / — | A only |
| B_noState → B_noSemantic | -19.79 | 16 | 206 | 162.61 | 3.04e-37 | 4.86e-36 | — | 3.07e-43 | 4.92e-42 | — | yes / — | A only |
| B_noSemantic → B_identityCore | +4.27 | 105 | 64 | 9.95 | 0.0016 | 0.0081 | — | 0.0020 | 0.0100 | — | yes / — | A only |
| B_identityCore → B_minimalCore | -39.58 | 0 | 380 | 380.00 | 1.24e-84 | 2.12e-83 | — | 8.12e-115 | 1.38e-113 | — | yes / — | A only |
| B_full → B_noState | +0.31 | 17 | 14 | 0.29 | 0.5900 | — | 1.0000 | 0.7201 | — | 1.0000 | — / no | B only |
| B_full → B_noSemantic | -19.48 | 17 | 204 | 158.23 | 2.76e-36 | — | 4.41e-35 | 6.92e-42 | — | 1.11e-40 | — / yes | B only |
| B_full → B_identityCore | -15.21 | 77 | 223 | 71.05 | 3.48e-17 | — | 4.87e-16 | 1.26e-17 | — | 1.69e-16 | — / yes | B only |
| B_full → B_minimalCore | -54.79 | 0 | 526 | 526.00 | 2.09e-116 | — | 3.56e-115 | 9.10e-159 | — | 1.55e-157 | — / yes | B only |
| B_noVolatile: F1 → F0 | -1.25 | 3 | 6 | 1.00 | 0.3173 | 0.6346 | 0.9519 | 0.5078 | 1.0000 | 1.0000 | no / no | — |
| B_noVolatile: F1 → F2 | -12.08 | 4 | 33 | 22.73 | 1.86e-06 | 2.05e-05 | 2.05e-05 | 1.08e-06 | 1.19e-05 | 1.19e-05 | yes / yes | — |
| B_noVolatile: F1 → F3 | +0.42 | 4 | 3 | 0.14 | 0.7055 | 0.7055 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | no / no | — |
| B_full → B_noVolatile, LOW pages | +15.00 | 77 | 5 | 63.22 | 1.85e-15 | 2.40e-14 | 2.40e-14 | 1.20e-17 | 1.57e-16 | 1.69e-16 | yes / yes | — |
| B_full → B_noVolatile, HIGH pages | +3.96 | 25 | 6 | 11.65 | 6.44e-04 | 0.0039 | 0.0039 | 8.78e-04 | 0.0053 | 0.0053 | yes / yes | — |
| LOW vs HIGH page-level Δ (exact permutation) | +11.04 | — | — | — | 0.0165 | 0.0495 | 0.0661 | 0.0165 | 0.0495 | 0.0661 | yes / no | **VERDICT CHANGED** |
| gpt-4.1: B_full×F1 → B_noVolatile×F1 | +9.58 | 26 | 3 | 18.24 | 1.95e-05 | 1.95e-04 | 1.95e-04 | 1.52e-05 | 1.52e-04 | 1.52e-04 | yes / yes | — |
| gpt-4.1-nano: B_full×F1 → B_noVolatile×F1 | +6.67 | 22 | 6 | 9.14 | 0.0025 | 0.0100 | 0.0125 | 0.0037 | 0.0149 | 0.0186 | yes / yes | — |
| claude-sonnet-4-6: B_full×F1 → B_noVolatile×F1 | +6.19 | 13 | 0 | 13.00 | 3.11e-04 | 0.0022 | 0.0022 | 2.44e-04 | 0.0022 | 0.0022 | yes / yes | — |
| fair subset: gpt-4.1 → claude-sonnet-4-6 | +4.25 | 69 | 32 | 13.55 | 2.32e-04 | 0.0021 | 0.0021 | 2.96e-04 | 0.0022 | 0.0022 | yes / yes | — |
| fair subset: gpt-4.1 → gpt-4.1-nano | -8.05 | 61 | 131 | 25.52 | 4.38e-07 | 5.25e-06 | 5.25e-06 | 4.81e-07 | 5.77e-06 | 5.77e-06 | yes / yes | — |
| COP cell: gpt-4.1 → o4-mini | +7.50 | 21 | 3 | 13.50 | 2.39e-04 | 0.0021 | 0.0021 | 2.77e-04 | 0.0022 | 0.0022 | yes / yes | — |

Shared-hypothesis verdict changes (χ² or exact): LOW vs HIGH page-level Δ (exact permutation).

## Table 2 cross-check

- B_full → B_noVolatile: +9.479167 pp; expected +9.48; PASS.
- B_full → B_noState: +0.312500 pp; expected +0.31; PASS.
- B_full → B_noSemantic: -19.479167 pp; expected -19.48; PASS.
- B_full → B_identityCore: -15.208333 pp; expected -15.21; PASS.
- B_full → B_minimalCore: -54.791667 pp; expected -54.79; PASS.

Additional controls: B_full→B_noVolatile b=102, c=11; B_full→B_minimalCore b=0. Cross-check mismatches: none.

This is sensitivity to hypothesis-family definition, not a new registered analysis. No LLM calls or network access occur in the script; all existing evidence and results are read-only.

## Input SHA-256

| Input | SHA-256 |
|---|---|
| experiments/analysis/bundle_ladder.py | 1c9b4b5b9e7a0dd1ba916e5a346593001c3fc61fa05a94bbed6fc16b7567454c |
| experiments/analysis/cross_model.py | 5e509ae19301f57cd195b012a622322164a99302e7488f0f848e40fad30ec9a0 |
| experiments/analysis/load.py | 36f12007478e812378e353e29df88b0bef8bd44b3d3e070ea86990e9bf457af7 |
| experiments/analysis/revision1_diagnostics.py | 4698eabd141613224a67299bef3bfd84452320b170166f97fa393d6c9661e656 |
| experiments/analysis/stats.py | 3010ce153461c31cad6cf8d1c01c5e20d16abe01cf9ffa5c8b8d8cf731df8508 |
| experiments/results/revision1/diagnostics.json | 7d1ac8223e83d7846c6cadbb65bb1144d1f03a760239910302fbc85cf780b4ca |
| experiments/results/revision1/diagnostics.md | 97b0f484082ad7aa08b5314eb2e43bdb1e1a65a59f1b2a5ce20911e88a6d7c42 |
| experiments/results/revision1/ladder_composition.md | 9d4b33bd8d5212393c65d90e877c834db6dfa878abe0280833349d9ad70291f0 |
| experiments/runs/axisc_claude-sonnet-4-6_page_01.jsonl | 51a18b9eb9f2bb1b2c2c76e922a909a87f6bd26ed2afbb5847301f19f4ad2999 |
| experiments/runs/axisc_claude-sonnet-4-6_page_02.jsonl | 54173093f7cf325d39b6f111d836a359cf147fe45a88ba0fbf2f26eab727e43d |
| experiments/runs/axisc_claude-sonnet-4-6_page_03.jsonl | 544cb09577d725b7023d47c1dfa326ce6bf2ce5235214f2dfcc5b973d3842527 |
| experiments/runs/axisc_claude-sonnet-4-6_page_04.jsonl | fc899f534cb226bec7e97b0367d9b7377904fa387a8aa08e1150a99bec65077f |
| experiments/runs/axisc_claude-sonnet-4-6_page_05.jsonl | bfba7812a69478fae98a94bbb42c9d01ba6dbe9cfc7ea7268453abdd8fec1efa |
| experiments/runs/axisc_claude-sonnet-4-6_page_06.jsonl | 6b69766785642c52144a0179466786efd702f791311909d42dbb129d23f89c3e |
| experiments/runs/axisc_claude-sonnet-4-6_page_07.jsonl | 95aa6608953791ce2676f24aee914f6ebd71788ff6a3b1d0654c3e0659e73213 |
| experiments/runs/axisc_claude-sonnet-4-6_page_08.jsonl | e7252ca268480f0431ff72a011b003e9e693a45228cdc47181ed4a6494a2ad63 |
| experiments/runs/axisc_claude-sonnet-4-6_page_09.jsonl | f3e72b31d8e6c06be8720e3be6b0b73e8ed364ce1028c97d29bf75d8f8184bb4 |
| experiments/runs/axisc_claude-sonnet-4-6_page_10.jsonl | 03820873307d48707f5dea733da51bcfad1b01431bd9d035300da67105e14b3f |
| experiments/runs/axisc_claude-sonnet-4-6_page_11.jsonl | a9771c25a89ad60e5c773f38ca8ebfdc92bac8e54a9d0bf376c1ecb1b7f570a9 |
| experiments/runs/axisc_claude-sonnet-4-6_page_12.jsonl | 9fb4930ab67fa6e9b831eb5b3f1673f491dd6763ad3d54306a506d90018318d3 |
| experiments/runs/axisc_claude-sonnet-4-6_page_13.jsonl | af6cae00d96fddd0b375f3aa74304a6e0a2508251236ed6f08e9c628755f81cd |
| experiments/runs/axisc_claude-sonnet-4-6_page_14.jsonl | b1dc507c3f9f48397cfbbb143ba9122b9b50d650607df1fccef029d0212f6f53 |
| experiments/runs/axisc_claude-sonnet-4-6_page_15.jsonl | b675c32e931ac53a0241d970f1149dff141bd6da6f29089eb1b64c99e0e5b4fe |
| experiments/runs/axisc_claude-sonnet-4-6_page_16.jsonl | 4638eb694fd8fc26f8086163ca6d064c22faa022ee8e03fdef980431e280c9ee |
| experiments/runs/axisc_claude-sonnet-4-6_page_18.jsonl | 9451711da479c56dc2163d62a73662ffaf3218f044f4cc094e679e8606749a66 |
| experiments/runs/axisc_claude-sonnet-4-6_page_19.jsonl | 0cb4d9d14883e710433136029add8bc9b324cb4718263f2b954b7fd4b76c489b |
| experiments/runs/axisc_claude-sonnet-4-6_page_20.jsonl | 5ec8127faf4e26380c9602851f99b8e06f8480e33c274a010b34560a28660f43 |
| experiments/runs/axisc_claude-sonnet-4-6_page_21.jsonl | 9342d02fa2d818e76ee5d6a604354e225160db75039a23ec482f62dd44bbd037 |
| experiments/runs/axisc_claude-sonnet-4-6_page_22.jsonl | 6144daad88b69c8111a49c560a8273e9b0556d04b4b3bc0db0f79aab8177e097 |
| experiments/runs/axisc_claude-sonnet-4-6_page_23.jsonl | 3f26d073d68152fc99a13949ba8aaa0e08e68873fc518d89b39301991b83ed5b |
| experiments/runs/axisc_claude-sonnet-4-6_page_24.jsonl | fb9f244ee2ac9992dd4b9f63bf65f8bb05b4bab860c48621e3b5dbe97257fba4 |
| experiments/runs/axisc_gpt-4-1-nano_page_01.jsonl | b5de08cfe8c752748fb3e9912b80d4119f3cd7eadafb7d651110d2b50bed8d48 |
| experiments/runs/axisc_gpt-4-1-nano_page_02.jsonl | 91fa17d8e4bb7489535b51f612a28fb5aaab0d83b677653ff41f6ec23b77f13c |
| experiments/runs/axisc_gpt-4-1-nano_page_03.jsonl | bf7a39e48d67e6d65fe3696cca652617381e93a3f62f950835d18584db99f611 |
| experiments/runs/axisc_gpt-4-1-nano_page_04.jsonl | e50063aa171f8d8ac64e35a8bbfb17e65bb28a2ed9fc26764789489a242c99c5 |
| experiments/runs/axisc_gpt-4-1-nano_page_05.jsonl | 56fbaa810cfb7febaffb954eb19d53c32c6e6c10b7bb5b7c00f24cf00a5533d3 |
| experiments/runs/axisc_gpt-4-1-nano_page_06.jsonl | 13bed73d83332b194294d2c30ef6e6f9ae7807b639bb3cd95d8886309b263ac8 |
| experiments/runs/axisc_gpt-4-1-nano_page_07.jsonl | 3163639454da98c0bcdbc9a068f28051274a2db88d26c1b7db1cf1d91feacc43 |
| experiments/runs/axisc_gpt-4-1-nano_page_08.jsonl | 3d92f8fbfdb206307a79be51f082a6fa46458b7f988f505ea5273392890119c1 |
| experiments/runs/axisc_gpt-4-1-nano_page_09.jsonl | 905703dffdb08ad130856ed043b9ccb1ed5b3cdbb1ff60d30617f43a48740e5a |
| experiments/runs/axisc_gpt-4-1-nano_page_10.jsonl | b1cf11c0bf03282473c3202ee9741dd08cf1edc1786dc1385a6f88266adf9123 |
| experiments/runs/axisc_gpt-4-1-nano_page_11.jsonl | 08351684173d041564aeab030d0d6c97fb6e4437a91eb0dc0214cc151128533b |
| experiments/runs/axisc_gpt-4-1-nano_page_12.jsonl | dde1da1b8a56831916e71381264bfdebf0f4ebc24a2a9a54bb53647730e87e87 |
| experiments/runs/axisc_gpt-4-1-nano_page_13.jsonl | af1e20616bdd33b6af58fc5c2143d0cd21637b071415734f9234840287b06899 |
| experiments/runs/axisc_gpt-4-1-nano_page_14.jsonl | 1428b9b1276a98b5caf34ec13b77037eaab2da7eebb67bd728ac1db09868b7a2 |
| experiments/runs/axisc_gpt-4-1-nano_page_15.jsonl | 2aeb3a9f0e9b551c05e72efaf4a1b3d20a812b461d426c58007e6f60440a16ef |
| experiments/runs/axisc_gpt-4-1-nano_page_16.jsonl | 589f22f0f262264964d873e64c17f9ec02d1226bded152ce6936ea63a1729cb3 |
| experiments/runs/axisc_gpt-4-1-nano_page_17.jsonl | 8ce085790250201c5f534e6921278a2a7039b947d1b37a8841d1bab79e49ca16 |
| experiments/runs/axisc_gpt-4-1-nano_page_18.jsonl | 623d14c137e93a92a19c76783fef677a9a8f29cc85d3d57910f24be09ed63cb8 |
| experiments/runs/axisc_gpt-4-1-nano_page_19.jsonl | 7892c7a3621b2965cbb42837ce6f4c8528e3c0ded88cda489ba6781edf2bee28 |
| experiments/runs/axisc_gpt-4-1-nano_page_20.jsonl | dec340c17d0cefeda2ca4e74038e0d2cdd7f55107ef2242deabca27767e4652c |
| experiments/runs/axisc_gpt-4-1-nano_page_21.jsonl | e58765f2cdbf1e174e01ca7899e817edd6bc07cfae16cf912394487ea6eb675d |
| experiments/runs/axisc_gpt-4-1-nano_page_22.jsonl | 16f784dc7c3d97cdef8167ad61f1ffd11ab2fd5d0be816ce33319fd8d4a81e3c |
| experiments/runs/axisc_gpt-4-1-nano_page_23.jsonl | 3db42a68e1906621f4b4ddec6dca66c7452ccf12d3ba16b58f16e095d54c4574 |
| experiments/runs/axisc_gpt-4-1-nano_page_24.jsonl | 84217f740239af4820197fc65c15955a0243d521e69b864eace7a74cf416a612 |
| experiments/runs/axisc_o4-mini_page_01.jsonl | b6c9b10dfe83d273d3fc1a2c9c9decd02ef78ce26bc25fdace2e1db06f62199e |
| experiments/runs/axisc_o4-mini_page_02.jsonl | 7747872342df82f21d583705398f1e072a7de8f529c508f8b4520608f2a22cac |
| experiments/runs/axisc_o4-mini_page_03.jsonl | df84bad9a5f7ccf478de5ece174e11704bf6c4791de2ea476193c2ba8d9ae559 |
| experiments/runs/axisc_o4-mini_page_04.jsonl | f9d7f02b107be78e26dac38ce54711bba2d8117949ae5a0b5fac91c3612a8380 |
| experiments/runs/axisc_o4-mini_page_05.jsonl | 80c807719ca4b511a3e3a9ed1682a2e3bbbf36fadfe5ea3e0fe59e1c8f65bd54 |
| experiments/runs/axisc_o4-mini_page_06.jsonl | 6a177342e112bce63ec209a04ae52cf7ba0d4ab17f60a2459520a683b994f9a0 |
| experiments/runs/axisc_o4-mini_page_07.jsonl | c89ce4e4f13280b3fa60b798807a6af130fb852e334315a440a5e63087b4d020 |
| experiments/runs/axisc_o4-mini_page_08.jsonl | 90915b36f3ea9d5d62dd925a5433b201b2a1436730a87f1acc75bd8b4266a623 |
| experiments/runs/axisc_o4-mini_page_09.jsonl | 0d26f4850ccfaf659cdfbea8ddc9880562e5b54fa6724695a24f7b4af4c8308f |
| experiments/runs/axisc_o4-mini_page_10.jsonl | b1183d7b70344922e8783e368bd7219b3a8aadba3f607adf6ea8203199c9579d |
| experiments/runs/axisc_o4-mini_page_11.jsonl | ed5a12899c72e3400c5ea5e04c72895db0d5726e04df1cfef3e53ece2a2ebfcf |
| experiments/runs/axisc_o4-mini_page_12.jsonl | 22022d86824cf32034434037c091d1186283cbc54136be23fc6a7a8be3936b9d |
| experiments/runs/axisc_o4-mini_page_13.jsonl | 8eb36d64c40eb79a9d0ed5cf8a69666f4b86336284a33876fc460b7ef5c843ef |
| experiments/runs/axisc_o4-mini_page_14.jsonl | cad70dc87d3c67cfdf384426749277b53f7909c1bab28a762c9bc25d388fceb3 |
| experiments/runs/axisc_o4-mini_page_15.jsonl | f1e80ad23ae272333956e0691ac9399bcdd87e28fd4dd0334ab17b06084edb8b |
| experiments/runs/axisc_o4-mini_page_16.jsonl | 3ce932f0d42fe8393b79e9aa6e3a01c2e20c4e3e9bb219efd1ea8590843ca727 |
| experiments/runs/axisc_o4-mini_page_17.jsonl | 279ecc838cc8ade08acce933b311b3fa1d14f3877ac442a3a5b5353d41994c46 |
| experiments/runs/axisc_o4-mini_page_18.jsonl | 945e8e3e1664e6c15353408de9c87c17a19d6329992ccc8a44bb0eaa883f9a75 |
| experiments/runs/axisc_o4-mini_page_19.jsonl | 30e730673e9679d2fcd388471bd21f968d17907123ebc89e7dae5892ffa410a3 |
| experiments/runs/axisc_o4-mini_page_20.jsonl | 5bd3d5f530bb5cbffd27a5c4569a5e80bcbb9908f3ac748eec3f39698b5f988a |
| experiments/runs/axisc_o4-mini_page_21.jsonl | 1bbdc472f00f086ff14793f68464de95fca4b8193168392c01f1130726a90666 |
| experiments/runs/axisc_o4-mini_page_22.jsonl | 05d6abbc8abcd49a663aabd62f9f4ea09796a48154e59fd97d056b0f01358633 |
| experiments/runs/axisc_o4-mini_page_23.jsonl | 06ee894c6c36e88c8833e08c9bb5c70226cef626d0ace7a3a3017d8786822078 |
| experiments/runs/axisc_o4-mini_page_24.jsonl | 03a7c22e15985ba5b75f238c27c3d496db6bc78454dc88b38772f6876d3cec2f |
| experiments/runs/matrix_page_01.jsonl | dd844783f07b722b1e97db8fe1a86c6bf161d805b810e483468e609b5bb22f0f |
| experiments/runs/matrix_page_02.jsonl | c5bc90fe1037e749f67623fd44c48d7ddff363438cc460f3c6215f2d2c0df68c |
| experiments/runs/matrix_page_03.jsonl | fdbb2aa8f8b3373951c40b8a602c93497727b394538da7f7572cd13c839a0802 |
| experiments/runs/matrix_page_04.jsonl | f350378f729742fcc4fe65d825d19185b185f6cacab65c7c267850acc06ab4f1 |
| experiments/runs/matrix_page_05.jsonl | 7e41442c079f72499bd04f20cd40bad4fed865cd285e43018ca42b9155f0fe0e |
| experiments/runs/matrix_page_06.jsonl | 1079c5782fca61ffd9a65e00c687e409dfafdac9ab458bd271eae9f4b077eb97 |
| experiments/runs/matrix_page_07.jsonl | 77329acb5ccd309f81d7bf1720a9f3f7c5885e8c5287aefcdfe6c66c47265613 |
| experiments/runs/matrix_page_08.jsonl | da02570ca76fd15c3c261598251554a42c1f46575d48c455780470d5bddb90db |
| experiments/runs/matrix_page_09.jsonl | 2c38d9ac1126cbe0769a59afd85149b8aebb73b0bd468b91aa58d5b5cf71b6bc |
| experiments/runs/matrix_page_10.jsonl | c7b75eb6f353f5da4b3ae00166178cc3bf265dfc5fbd95f8149e19bd37b2d762 |
| experiments/runs/matrix_page_11.jsonl | e9a80227c4c8b1c6902976632ac53e33ba3b684e345d10e2d57276d16660de6b |
| experiments/runs/matrix_page_12.jsonl | 2fab16bc4c57507c5df41e152278fcebc4af9d7214fa3d35ffbad55db2671e44 |
| experiments/runs/matrix_page_13.jsonl | 6e34d9107336c329e8f38d6cbd1af570e71555bfb1b100a67469aff522420af7 |
| experiments/runs/matrix_page_14.jsonl | bf55272988b458d87c237ec0ab81829aa7b074d77b20e6670e9dc7312cf0100e |
| experiments/runs/matrix_page_15.jsonl | f9b675ee7f361800b1d5ec659daca8df9a3eabdba02385898adc870bbcb75213 |
| experiments/runs/matrix_page_16.jsonl | ba14628953f4b05c5c7b685fc7100a6f9a201186e3f3497aab596c969575cffd |
| experiments/runs/matrix_page_17.jsonl | 69b2d93142e1b1923c790c26281be8fd9902155dc2718f90a5e5aab8624f08da |
| experiments/runs/matrix_page_18.jsonl | 2d6ba548dee1611dfa9fa5d580136fe534d7c43711d696f9b386716f4e59992f |
| experiments/runs/matrix_page_19.jsonl | 44644bdd30669eecb854e788d4de1eab0965bb03d8f7e6f0be1a152701a5f786 |
| experiments/runs/matrix_page_20.jsonl | 2fcc7b98833914dc547c8c061f46a28f8427f768287cf7d64bcd74a085a54da2 |
| experiments/runs/matrix_page_21.jsonl | 503f69938ea919c170ca318c4f6a0a75c4b3f785a2be1efcdcf51c6fbb423990 |
| experiments/runs/matrix_page_22.jsonl | 6e290435ef7abcd9d8118d9e7161d4561f1c4de6615d91a3154c722c699da36b |
| experiments/runs/matrix_page_23.jsonl | 6cf434a09195baac2fefd65b9d5cbc926a57b2383d6b30f40165d9173e7fc83c |
| experiments/runs/matrix_page_24.jsonl | 4faad883038e68cf209da3362589de3fd353ae5a8df92ac2d27be76803d0eba4 |
