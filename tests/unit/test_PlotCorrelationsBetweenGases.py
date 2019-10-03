import sys
import os
myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + '/../../')
import src.silicone.PlotCorrelationsBetweenGases as PlotCorrelationsBetweenGases
import pandas as pd
import re

def test_PlotCorrelationsBetweenGases(check_aggregate_df):
    years_of_interest = [2010]
    save_results = None
    # if non-null, also plot these quantiles.
    plot_quantiles = [0.2, 0.5, 0.8]
    # if non-null, save data on the quantiles too
    quantiles_savename = '../../Output/TestQuantiles/'
    # How many boxes are used to fit the quantiles?
    quantile_boxes = 3
    # Should we extend the quantile boxes by an additional factor?
    quantile_decay_factor = 1
    # use a smoothing spline? If None, don't. Otherwise this is the smoothing factor, s, used in the spline model.
    smoothing_spline = 10
    # Color different models different colours?
    model_colours = True
    # In the model-coloured version, how much does the figure need to be reduced by to leave room for the legend?
    legend_fraction = 0.65
    # ________________________________________________________

    # Clean the ouput folder before we start.
    output_files = os.listdir(quantiles_savename)
    for output_file in output_files:
        if output_file[-9:] != 'gitignore':
            os.remove(quantiles_savename + output_file)

    # Run the first set of parameters
    PlotCorrelationsBetweenGases.plot_emission_correlations(check_aggregate_df, years_of_interest, save_results,
                                    plot_quantiles, quantiles_savename, quantile_boxes, quantile_decay_factor,
                                    smoothing_spline, model_colours, legend_fraction)
    quantiles_files = os.listdir(quantiles_savename)
    assert quantiles_files[1][0:4] == 'CO2_'
    regex_match = re.compile(".*" + str(years_of_interest[0]) + "\.csv")
    csv_files = [x for x in quantiles_files if regex_match.match(x)]
    with open(quantiles_savename + csv_files[2]) as csv_file:
        csv_reader = pd.read_csv(csv_file, delimiter=',')
        assert csv_reader.iloc[1, 1] == 217
    for csv_file in csv_files:
        os.remove(quantiles_savename + csv_file)

    # Rerun the code with slightly different parameters.
    plot_quantiles = None
    save_results = '../../Output/TestQuantiles/'
    model_colours = False
    PlotCorrelationsBetweenGases.plot_emission_correlations(check_aggregate_df, years_of_interest, save_results,
                                    plot_quantiles, quantiles_savename, quantile_boxes, quantile_decay_factor,
                                    smoothing_spline, model_colours, legend_fraction)
    quantiles_files = os.listdir(quantiles_savename)
    csv_files = [x for x in quantiles_files if regex_match.match(x)]
    assert len(csv_files) == 2
    for csv_file in csv_files:
        os.remove(quantiles_savename + csv_file)
    regex_match = re.compile(".*" + str(years_of_interest[0]) + "\.png")
    png_files = [x for x in quantiles_files if regex_match.match(x)]
    assert len(png_files) == 4
    for png_file in png_files:
        os.remove(quantiles_savename + png_file)
    output_files = os.listdir(quantiles_savename)
    assert len(output_files) == 1