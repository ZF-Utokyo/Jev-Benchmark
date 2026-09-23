/* Aggregate metrics recomputed from the frozen benchmark release. */
window.JEV_RESULTS = [
  {
    "key": "jev",
    "name": "Jev 1.13.0",
    "short": "Jev",
    "kind": "jev",
    "accuracy": 77.3792443806791,
    "accuracyCI": [
      75.9923481587757,
      78.81396461023434
    ],
    "cost": 0.00022805078048780488,
    "time": 1.244225677997747,
    "all12": 23,
    "states": {
      "all12_correct": 23,
      "stable_wrong": 5,
      "changed_valid": 2,
      "invalid": 0
    },
    "all12CI": [
      60.0,
      90.0
    ]
  },
  {
    "key": "gemini-flash-lite",
    "name": "Gemini 3.5 Flash-Lite",
    "short": "Flash-Lite",
    "kind": "hosted",
    "accuracy": 82.54423720707796,
    "accuracyCI": [
      81.10951697752272,
      83.9789574366332
    ],
    "cost": 0.0013530991869918692,
    "time": 1.600282021005114,
    "all12": 21,
    "states": {
      "all12_correct": 21,
      "stable_wrong": 4,
      "changed_valid": 5,
      "invalid": 0
    },
    "all12CI": [
      53.333333333333336,
      83.33333333333334
    ]
  },
  {
    "key": "gemini-pro",
    "name": "Gemini 3.1 Pro Preview",
    "short": "Gemini Pro",
    "kind": "hosted",
    "accuracy": 83.21377331420373,
    "accuracyCI": [
      81.68340506934481,
      84.7919655667145
    ],
    "cost": 0.008474292682926826,
    "time": 3.734850553002616,
    "all12": 22,
    "states": {
      "all12_correct": 22,
      "stable_wrong": 2,
      "changed_valid": 5,
      "invalid": 1
    },
    "all12CI": [
      56.666666666666664,
      86.66666666666667
    ]
  },
  {
    "key": "luna",
    "name": "GPT-5.6 Luna",
    "short": "Luna",
    "kind": "hosted",
    "accuracy": 78.95743663318986,
    "accuracyCI": [
      77.18794835007174,
      80.6312769010043
    ],
    "cost": 0.0009314890243902442,
    "time": 1.7391113769990625,
    "all12": 22,
    "states": {
      "all12_correct": 22,
      "stable_wrong": 3,
      "changed_valid": 5,
      "invalid": 0
    },
    "all12CI": [
      56.666666666666664,
      86.66666666666667
    ]
  },
  {
    "key": "terra",
    "name": "GPT-5.6 Terra",
    "short": "Terra",
    "kind": "hosted",
    "accuracy": 82.5920612147298,
    "accuracyCI": [
      81.15734098517456,
      84.02678144428502
    ],
    "cost": 0.011838578861788613,
    "time": 11.608725181009504,
    "all12": 20,
    "states": {
      "all12_correct": 20,
      "stable_wrong": 2,
      "changed_valid": 8,
      "invalid": 0
    },
    "all12CI": [
      50.0,
      83.33333333333334
    ]
  },
  {
    "key": "astra",
    "name": "GPT-6 Astra",
    "short": "Astra",
    "kind": "hosted",
    "accuracy": 81.82687709230034,
    "accuracyCI": [
      80.20086083213774,
      83.35724533715926
    ],
    "cost": 0.09188973577235769,
    "time": 20.944281117001083,
    "all12": 22,
    "states": {
      "all12_correct": 22,
      "stable_wrong": 6,
      "changed_valid": 2,
      "invalid": 0
    },
    "all12CI": [
      56.666666666666664,
      86.66666666666667
    ]
  },
  {
    "key": "claude-haiku45",
    "name": "Claude Haiku 4.5",
    "short": "Haiku 4.5",
    "kind": "hosted",
    "accuracy": 79.43567670970828,
    "accuracyCI": [
      77.80966044954567,
      81.110712577714
    ],
    "cost": 0.005395666666666669,
    "time": 5.654496460003429,
    "all12": 19,
    "states": {
      "all12_correct": 19,
      "stable_wrong": 2,
      "changed_valid": 9,
      "invalid": 0
    },
    "all12CI": [
      46.666666666666664,
      80.0
    ]
  },
  {
    "key": "claude-sonnet5",
    "name": "Claude Sonnet 5",
    "short": "Sonnet 5",
    "kind": "hosted",
    "accuracy": 82.40076518412242,
    "accuracyCI": [
      80.9660449545672,
      83.83548541367767
    ],
    "cost": 0.011351934959349594,
    "time": 3.2703747140039923,
    "all12": 24,
    "states": {
      "all12_correct": 24,
      "stable_wrong": 1,
      "changed_valid": 5,
      "invalid": 0
    },
    "all12CI": [
      63.33333333333333,
      93.33333333333333
    ]
  },
  {
    "key": "qwen4b",
    "name": "Qwen3.5-4B",
    "short": "Qwen 4B",
    "kind": "local",
    "accuracy": 74.22285987565758,
    "accuracyCI": [
      70.58823529411765,
      77.3792443806791
    ],
    "cost": 0.05365257818485553,
    "time": 86.8687637559924,
    "all12": 17,
    "states": {
      "all12_correct": 17,
      "stable_wrong": 2,
      "changed_valid": 8,
      "invalid": 3
    },
    "all12CI": [
      40.0,
      73.33333333333333
    ]
  },
  {
    "key": "qwen9b",
    "name": "Qwen3.5-9B",
    "short": "Qwen 9B",
    "kind": "local",
    "accuracy": 79.14873266379723,
    "accuracyCI": [
      76.80535628885701,
      81.2051649928264
    ],
    "cost": 0.07736060416892426,
    "time": 134.6441764360061,
    "all12": 18,
    "states": {
      "all12_correct": 18,
      "stable_wrong": 2,
      "changed_valid": 8,
      "invalid": 2
    },
    "all12CI": [
      43.333333333333336,
      76.66666666666667
    ]
  }
];
