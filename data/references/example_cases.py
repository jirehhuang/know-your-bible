## Assuming example_cases is defined as per user input:
example_cases = [
	{
        "sentence": "note on 1 John 3:20",  # Single verse, some of which start with numbers
        "references": [
            {
                "reference": "1 John 3:20",
                "book": "1 John",
                "chapters": [
                        "1 John 3"
                    ],
                "verses": [
                    "1 John 3:20"
                ]
            }
        ]
	},
	{
		"sentence": "note on Hebrews 9:11-12",  # Range of verses
		"references": [
            {
                "reference": "Hebrews 9:11-12",
                "book": "Hebrews",
                "chapters": [
                    "Hebrews 9"
                ],
                "verses": [
                    "Hebrews 9:11",
                    "Hebrews 9:12"
                ]
            }
        ]
	},
	{
		"sentence": "note on Genesis 17:26-18:2 - Nothing is too hard for God",  # Range of verses across chapters
		"references": [
            {
                "reference": "Genesis 17:26-18:2",
                "book": "Genesis",
                "chapters": [
                    "Genesis 17",
                    "Genesis 18"
                ],
                "verses": [
                    "Genesis 17:26",
                    "Genesis 17:27",
                    "Genesis 18:1",
                    "Genesis 18:2"
                ]
            }
        ]
	},
	{
		"sentence": "Job 1:6 , 12 , 21-22 ; 2:6-7",  # Comma and/or semi-colon separating references to different chapters of a single book, with spaces
		"references": [
            {
                "reference": "Job 1:6 , 12 , 21-22 ; 2:6-7",
                "book": "Job",
                "chapters": [
                    "Job 1",
                    "Job 2"
                ],
                "verses": [
                    "Job 1:6",
                    "Job 1:12",
                    "Job 1:21",
                    "Job 1:22",
                    "Job 2:6",
                    "Job 2:7"
                ]
            }
        ]
	},
	{
		"sentence": "note on Jude 3-4 - Grace liberates us",  # Books with only 1 chapter: should be converted to Jude 1:3-4 since BIBLE[”Jude”] only contains chapter key "1"
		"references": [
            {
                "reference": "Jude 3-4",
                "book": "Jude",
                "chapters": [
                    "Jude 1"
                ],
                "verses": [
                    "Jude 1:3",
                    "Jude 1:4"
                ]
            }
        ]
	},
	{
		"sentence": "note on 2 Corinthians 4:7-8 - The Christian life; From the note on Ecclesiastes 1:14 - Ecclesiastes was written",  # References with trailing dash (should extract 2 Corinthians 4:7-18 and Ecclesiastes 1:14)
		"references": [
            {
                "reference": "2 Corinthians 4:7-8",
                "book": "2 Corinthians",
                "chapters": [
                    "2 Corinthians 4"
                ],
                "verses": [
                    "2 Corinthians 4:7",
                    "2 Corinthians 4:8"
                ]
            },
            {
                "reference": "Ecclesiastes 1:14",
                "book": "Ecclesiastes",
                "chapters": [
                    "Ecclesiastes 1"
                ],
                "verses": [
                    "Ecclesiastes 1:14"
                ]
            }
        ]
	},
	{
		"sentence": "note on Song of Solomon 5:16-6:1 - Jesus will ultimately",  # Another example of range across chapters with trailing dash
		"references": [
            {
                "reference": "Song of Solomon 5:16-6:1",
                "book": "Song of Solomon",
                "chapters": [
                    "Song of Solomon 5",
                    "Song of Solomon 6"
                ],
                "verses": [
                    "Song of Solomon 5:16",
                    "Song of Solomon 6:1"
                ]
            }
        ]
	},
	{
		"sentence": "note on Ecclesiastes 2:24-26a - If we neglect",  # Partial verses should be treated as whole
		"references": [
            {
                "reference": "Ecclesiastes 2:24-26",
                "book": "Ecclesiastes",
                "chapters": [
                    "Ecclesiastes 2"
                ],
                "verses": [
                    "Ecclesiastes 2:24",
                    "Ecclesiastes 2:25",
                    "Ecclesiastes 2:26"
                ]
            }
        ]
	},
	{
		"sentence": "work of God in Christ ( 1 Corinthians 15:55 7 )",  # Trailing number(s) after refrence separated by space: should be just be 1 Corinthians 15:55 (the 7 is a footnote)
		"references": [
            {
                "reference": "1 Corinthians 15:55",
                "book": "1 Corinthians",
                "chapters": [
                    "1 Corinthians 15"
                ],
                "verses": [
                    "1 Corinthians 15:55"
                ]
            }
        ]
	},
	{
		"sentence": "Romans 16:20 1 Corinthians 1:3 / 1 Corinthians 16:23 2 Corinthians 1:2",  # Many verses, some only separated by spaces
		"references": [
            {
                "reference": "Romans 16:20",
                "book": "Romans",
                "chapters": [
                    "Romans 16"
                ],
                "verses": [
                    "Romans 16:20"
                ]
            },
            {
                "reference": "1 Corinthians 1:3",
                "book": "1 Corinthians",
                "chapters": [
                    "1 Corinthians 1"
                ],
                "verses": [
                    "1 Corinthians 1:3"
                ]
            },
            {
                "reference": "1 Corinthians 16:23",
                "book": "1 Corinthians",
                "chapters": [
                    "1 Corinthians 16"
                ],
                "verses": [
                    "1 Corinthians 16:23"
                ]
            },
            {
                "reference": "2 Corinthians 1:2",
                "book": "2 Corinthians",
                "chapters": [
                    "2 Corinthians 1"
                ],
                "verses": [
                    "2 Corinthians 1:2"
                ]
            }
        ]
	},
	{
		"sentence": "please turn to 1 John 2:35-1 where",  # Invalid backwards range with invalid start
		"references": []
    },
	{
		"sentence": "please turn to 1 Peter 3:15-1 where",  # Invalid backwards range
		"references": [
            {
                "reference": "1 Peter 3:15-1",  # Extract reference as is
                "book": "1 Peter",
                "chapters": [
                    "1 Peter 3"
                ],
                "verses": [
                    "1 Peter 3:15"  # Only keep first verse; do not iterate backwards (print warning)
                ]
            }
        ]
    },
	{
		"sentence": "(See Ephesians 5:33-34 ;",  # Print warning for invalid verses: Ephesians 5:34 does not exist
		"references": [
            {
                "reference": "Ephesians 5:33-34",  # Extract reference as is
                "book": "Ephesians",
                "chapters": [
                    "Ephesians 5"
                ],
                "verses": [
                    "Ephesians 5:33"  # Only keep first verse; there is no Ephesians 5:34 (print warning)
                ]
            }
        ]
	},
	{
		"sentence": "even stronger in 2 Corinthians 9: It is the grace of God",  # Incomplete references that do not indicate specific verse(s) should be skipped
		"references": []
	},
    {
        "sentence": "(see 2 Corinthians 6:18 - 7:1 ; 13:2 ; ",  # Ranges across chapters and additional verses
        "references": [
            {
                "reference": "2 Corinthians 6:18-7:1 ; 13:2",
                "book": "2 Corinthians",
                "chapters": [
                    "2 Corinthians 6",
                    "2 Corinthians 7",
                    "2 Corinthians 13"
                ],
                "verses": [
                    "2 Corinthians 6:18",
                    "2 Corinthians 7:1",
                    "2 Corinthians 13:2"
                ]
            }
        ]
    },
]
