from os.path import join, isdir
from os import mkdir
import matplotlib.pyplot as plt
import numpy as np
from acoular import Calib, TimeSamples, PowerSpectra

from pyTransmission import Measurement_E2611, MicSwitchCalib_E2611


def test_two_load_method():
    ##############################################################################
    # USER INPUT:
    ##############################################################################

    # ---------------- Amplitude Calibration (with regular calibrator) -----------
    # (use create_calib_factor_xml_file.py to convert raw csv files to xml):
    calibpath = './Resources'
    calibfile = 'calib.xml'
    calibration = Calib(from_file=join(calibpath, calibfile))

    # ---------------- Amplitude and Phase Correction Measurements ---------------
    # relative path of the time data files (.h5 data format)
    soundfilepath = './Resources/'

    # filename of empty measurement with direct configuration:
    filename_direct = 'empty_00_11_22_33_44_55.h5'
    #channels of switched mic and filenames of measurements with switched configurations
    filenames_switched = {1: 'empty_01_10_22_33_44_55.h5',  # <- here 2nd mic (index 1) was switched w/ ref (index 0)
                          2: 'empty_02_11_20_33_44_55.h5',
                          3: 'empty_03_11_22_30_44_55.h5',
                          4: 'empty_04_11_22_33_40_55.h5',
                          5: 'empty_05_11_22_33_44_50.h5'}

    # reference channel
    # important: The reference Channel has to be 0 for the amplitude/phase correction to work!:
    ref_channel = 0

    # Mic channels in positions 1-4 of the narrow and wide configuration
    # (if the channels are sorted in increasing ordner from next to loudspeaker
    # to far away from loudspeaker, this ordering is correct)
    mic_channels_narrow = [1, 2, 3, 4]
    mic_channels_wide = [0, 2, 3, 5]

    # Filenames of the measurements (One file in each list for each measurement):
    # (in the same directory as the other sound files):
    # First load case:
    filenames_measurement_one_load = ['measurement_one_load.h5',  # you can add files here
                                      ]
    # Second load case:
    filenames_measurement_two_load = ['measurement_two_load.h5',  # you can add files here
                                      ]

    # Parameters for frequency data handling:
    block_size = 4*2048
    window = 'Hanning'
    overlap = '50%'
    cached = False

    # Parameters for plot:
    savePlot = False
    plotpath = './Plots'

    ##############################################################################
    # CALCULATION: No user input from here on
    ##############################################################################

    # ---------------- Amplitude and Phase Correction  ---------------------------

    # get timedata of direct configuration:
    time_data = TimeSamples(
        name=join(soundfilepath, filename_direct), calib=calibration)

    # get frequency data / csm of direct configuration:
    freq_data = PowerSpectra(time_data=time_data,
                             block_size=block_size,
                             window=window,
                             overlap=overlap,
                             cached=cached)

    # initialize correction transferfunction with ones so the
    # ref-ref transfer function stays as ones, which is correct
    H_c = np.ones((freq_data.csm.shape[0:2]), dtype=complex)

    # iterate over all switched configurations:
    for i in filenames_switched:
        # get timedata of switched configuration:
        time_data_switched = TimeSamples(
            name=join(soundfilepath, filenames_switched[i]), calib=calibration)

        # get frequency data of switched configuration:
        freq_data_switched = PowerSpectra(time_data=time_data_switched,
                                          block_size=freq_data.block_size,
                                          window=freq_data.window,
                                          cached=freq_data.cached)

        # calculate amplitude/phase correction for switched channel:
        calib = MicSwitchCalib_E2611(freq_data=freq_data,
                                     freq_data_switched=freq_data_switched,
                                     ref_channel=0,
                                     test_channel=i)

        # store result:
        H_c[:, i] = calib.H_c

    # ---------------- Measurement  ----------------------------------------------
    # iterate over all measurements
    for filename_measurement_one_load, filename_measurement_two_load in zip(filenames_measurement_one_load,
                                                                            filenames_measurement_two_load):
        td_one_load = TimeSamples(name=join(soundfilepath, filename_measurement_one_load),
                                  calib=calibration)

        td_two_load = TimeSamples(name=join(soundfilepath, filename_measurement_two_load),  # TODO: add actual second load case
                                  calib=calibration)

        # get frequency data / csm:
        freq_data_one_load = PowerSpectra(time_data=td_one_load,
                                          block_size=block_size,
                                          window=window,
                                          overlap=overlap,
                                          cached=cached)

        freq_data_two_load = PowerSpectra(time_data=td_two_load,
                                          block_size=block_size,
                                          window=window,
                                          overlap=overlap,
                                          cached=cached)

        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        # use both narrow and wide microphone positions for lower and higher frequencies:
        for spacing in ['wide', 'narrow']:
            if spacing == 'narrow':
                s1 = s2 = 0.085  # distance between mics
                mic_channels = mic_channels_narrow  # indices of microphones #1-#4

            elif spacing == 'wide':
                s1 = s2 = 0.5  # distance between mics
                mic_channels = mic_channels_wide

            msm1 = Measurement_E2611(freq_data=freq_data_one_load,
                                     freq_data_two_load=freq_data_two_load,
                                     method='two load',
                                     s1=s1,  # distance between mic #1 and #2
                                     s2=s2,  # distance between mic #3 and #4
                                     ref_channel=ref_channel,  # index of the reference microphone
                                     mic_channels=mic_channels,  # indices of the microphones in positions 1-4
                                     H_c=H_c)  # Amplitude/Phase Correction factors

            #switched first and second load case
            msm2 = Measurement_E2611(freq_data=freq_data_two_load,
                                     freq_data_two_load=freq_data_one_load,
                                     method='two load',
                                     s1=s1,  # distance between mic #1 and #2
                                     s2=s2,  # distance between mic #3 and #4
                                     ref_channel=ref_channel,  # index of the reference microphone
                                     mic_channels=mic_channels,  # indices of the microphones in positions 1-4
                                     H_c=H_c)  # Amplitude/Phase Correction factors

            # get fft frequencies
            freqs1 = msm1.freq_data.fftfreq()
            freqs2 = msm2.freq_data.fftfreq()
            assert(np.allclose(freqs1, freqs2))

            # get transfer_matric
            T1 = msm1.transfer_matrix
            T2 = msm2.transfer_matrix
            assert (np.allclose(T1, T2, equal_nan=True))

            # get transmission factor
            t1 = msm1.transmission_coefficient
            t2 = msm2.transmission_coefficient
            assert(np.allclose(t1, t2, equal_nan=True))

            # calculate transmission loss
            transmission_loss1 = msm1.transmission_loss
            transmission_loss2 = msm2.transmission_loss
            assert(np.allclose(transmission_loss1,
                   transmission_loss2, equal_nan=True))

            # if needed: calculate Impedance, plotting is the same
            z1 = msm1.z
            z2 = msm2.z
            assert(np.allclose(z1, z2, equal_nan=True))

            # get frequency working range
            freqrange1 = msm1.working_frequency_range
            freqrange2 = msm2.working_frequency_range
            assert(np.allclose(freqrange1, freqrange2, equal_nan=True))


if __name__ == "__main__":
    test_two_load_method()
    print("Everything passed")
