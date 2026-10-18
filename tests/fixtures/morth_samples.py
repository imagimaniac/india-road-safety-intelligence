"""Fixtures for parser tests."""

import textwrap


MO_NATIONAL_SERIES_SAMPLE = textwrap.dedent(
    """\
    Annexure 1
    Road Accidents, Persons Killed and Injured: 1970-2022

    1970 1,14,100 14,500 70,100 5,39,000 1,401 21.2 814.4 959.8 2.7 103.5 122.0 13.0 500.4 589.7
    1980 1,53,200 24,000 1,09,100 6,73,000 4,521 22.8 338.9 1,026.9 3.6 53.1 160.9 16.2 241.3 731.3
    2000 3,91,449 78,911 3,99,265 10,14,825 48,857 38.6 80.1 1,180.5 7.8 16.2 238.0 39.3 81.7 1,204.0
    2010 4,99,628 1,34,513 5,27,512 11,76,742 1,27,746 42.5 39.1 1,090.3 11.4 10.5 293.5 44.8 41.3 1,151.2
    2020 3,72,181 1,38,383 3,46,747 13,26,155 3,26,299
    2021 4,12,432 1,53,972 3,84,448 13,63,006 30.3 11.3 28.2
    2022 4,61,312 1,68,491 4,43,366 13,75,586 33.5 12.2 32.2
    """
)


MO_PREFACE_SAMPLE = textwrap.dedent(
    """\
    During 2022, a total of 4,61,312 accidents were recorded in the country, of
    which, 1,51,997 (32.9%) took place on the National Highways (NH) including
    Expressways, 1,06,682 (23.1%) on State Highways (SH) and the remaining
    2,02,633 (43.9%) on Other Roads. Out of the total of 1,68,491 fatalities reported in
    2022, 61,038 (36.2%) were on National Highways, 41,012 (24.3%) were on State
    Highways and 66,441 (39.4%) were on Other Roads.

    'over speeding' constitute the main violation associated with accidents,
    fatalities and injuries, in 2022. During 2022, 'over speeding' accounting for
    72.3 percent of the total road accidents, 71.2 percent of total deaths and 72.8
    percent of total injuries.
    """
)


STATE_CSV_SAMPLE = textwrap.dedent(
    """\
    Sl No,State,2020 Accidents,2021 Accidents,2022 Accidents,2023 Accidents,2024 Accidents,Change from 2023 to 2024,% change from 2023 to 2024,2020 Ranking,2021 Ranking,2022 Ranking,2023 Ranking,2024 Ranking
    1,Andhra Pradesh,"19,509","21,556","21,249","19,949","19,557",-392,-2,7,7,9,9,9
    2,Maharashtra,"30,348","29,878","33,320","33,056","34,222",1,166,3.5,6,6,6,6,6
    3,Tamil Nadu,"45,484","55,682","64,105","67,238","66,160",-1,078,-1.6,3,3,2,2,2
    4,Uttar Pradesh,"30,593","36,040","41,746","44,534","40,712",-3,822,-8.6,5,5,4,4,4
    """
)


GNCAP_RESULTS_SAMPLE = textwrap.dedent(
    """\
    <html><body>
    <h2 style="white-space:pre-wrap;"><strong>Tata Nexon (*) &#8211; 2 Airbags</strong></h2>
    <p class="" style="white-space:pre-wrap;">Tested model: Tata Nexon, RHD<br>Body type: 5 Door SUV<br>Year of publication: 2018</p>
    <p class="" style="white-space:pre-wrap;"><a href="/s/SaferCarsForIndia-Tata-Nexon.pdf" target="_blank">Download full fact sheet</a></p>
    <h2 style="white-space:pre-wrap;"><strong>Mahindra XUV700 (*) &#8211; 2 Airbags</strong></h2>
    <p class="" style="white-space:pre-wrap;">Tested model: Mahindra XUV700, RHD<br>Body type: 5 Door SUV<br>Year of publication: 2021</p>
    <p class="" style="white-space:pre-wrap;"><a href="/s/SaferCarsForIndia-Mahindra-XUV700-2021-fact-sheet.pdf" target="_blank">Download full fact sheet</a></p>
    </body></html>
    """
)


GNCAP_FACT_SHEET_SAMPLE = textwrap.dedent(
    """\
    Adult Occupant Protection
    16.06 max. 17.00 Adult
    Child Occupant Protection
    25.00 max. 49.00 Child

    The bodyshell was rated as stable.

    Safety equipment includes dual airbags, ABS and ISOFIX.
    """
)