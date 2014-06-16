from scipy.spatial.distance import pdist, squareform
from collections import defaultdict
import sys
from .._cargo_commonObjects import cargo
from .._barge_utils import FlotillaFactory

class Data(FlotillaFactory):
    """Generic study_data model for both splicing and expression study_data

    Attributes
    ----------


    Methods
    -------

    """

    def __init__(self, sample_metadata, species=None):
        self._default_reducer_args = {'whiten':False, 'show_point_labels':False, 'show_vectors':False}
        self.samplewise_reduction = {}
        self.featurewise_reduction = {}
        self.clf_dict = {}
        self.localZ_dict = {}
        self.lists = {}
        self.pca_plotting_args = {}
        self._default_featurewise=False
        self._last_reducer_accessed = None
        self._last_predictor_accessed = None
        self._default_group_id = 'any_cell'
        self._default_list_id = 'variant'
        self.cargo = cargo
        self.sample_metadata = sample_metadata
        self.set_reducer_colors()
        self.set_reducer_markers()
        self.species=species

    def set_reducer_colors(self):
        try:
            self._default_reducer_args.update({'colors_dict':self.sample_metadata.color})
        except:
            sys.stderr.write("color loading failed")
            self._default_reducer_args.update({'colors_dict':defaultdict(lambda : 'r')})

    def set_reducer_markers(self):
        try:
            self._default_reducer_args.update({'markers_dict':self.sample_metadata.marker})
        except:
            sys.stderr.write("marker loading failed")
            self._default_reducer_args.update({'markers_dict': defaultdict(lambda : 'o')})

    def set_outliers(self):
        self.outliers = set(self.sample_metadata['outlier'].ix[map(bool, self.sample_metadata['outlier'])].index)

    def get_outliers(self):
        try:
            return self.outliers
        except AttributeError:
            self.set_outliers()
            return self.outliers

    def drop_outliers(self, df):
        assert 'outlier' in self.sample_metadata.columns
        these_outliers = self.get_outliers().intersection(set(df.index))
        print "dropping ", these_outliers
        return df.drop(these_outliers)


    def calculate_distances(self, metric='euclidean'):
        """Creates a squareform distance matrix for clustering fun

        Needed for some clustering algorithms

        Parameters
        ----------
        metric : str
            One of any valid scipy.distance metric strings
        """
        raise NotImplementedError
        self.pdist = squareform(pdist(self.binned, metric=metric))
        return self

    def correlate(self, method='spearman', between='measurements'):
        """Find correlations between either splicing/expression measurements
        or cells
        """
        raise NotImplementedError

    def jsd(self):
        """Jensen-Shannon divergence showing most varying measurements within a
        celltype and between celltypes

        Returns
        -------
        fig : matplotlib.Figure
            A figure object for saving.
        """
        raise NotImplementedError

    def _echo(self, x):
        return x

    #_naming_fun converts input feature names to something else. by default, just echo.
    _naming_fun = _echo

    def get_naming_fun(self):
        return self._naming_fun

    def set_naming_fun(self, fun, test_name='foo'):
        self._naming_fun = fun
        try:
            fun(test_name)
        except:
            pass
            #print "might not be a good naming function, failed on %s" % test_name


    def plot_classifier(self, gene_list_name=None, sample_list_name=None, clf_var=None,
                        predictor_args=None, plotting_args=None):

        """Principal component-like analysis of measurements
        Params
        -------
        obj_id - key of the object getting plotted
        group_id -
        categorical_trait - classifier feature
        list_name - subset of genes to use for building class



        Returns
        -------
        self
        """
        if predictor_args is None:
            predictor_args = {}

        if plotting_args is None:
            plotting_args = {}

        local_plotting_args = self.pca_plotting_args.copy()
        local_plotting_args.update(plotting_args)

        clf = self.get_predictor(gene_list_name=gene_list_name,
                                 sample_list_name=sample_list_name,
                                 clf_var=clf_var,
                                 **predictor_args)
        clf(plotting_args=local_plotting_args)

        return self

    def plot_dimensionality_reduction(self, x_pc=1, y_pc=2, obj_id=None, group_id=None,
                                      list_name=None, featurewise=None, **plotting_args):

        """Principal component-like analysis of measurements

        Returns
        -------
        self
        """
        local_plotting_args = self.pca_plotting_args.copy()
        local_plotting_args.update(plotting_args)
        pca = self.get_reduced(obj_id, list_name, group_id, featurewise=featurewise)
        pca(markers_size_dict=lambda x: 400,
            show_vectors=False,
            title_size=10,
            axis_label_size=10,
            x_pc = "pc_" + str(x_pc), #this only affects the plot, not the study_data.
            y_pc = "pc_" + str(y_pc), #this only affects the plot, not the study_data.
            **local_plotting_args
            )
        return self

    def get_reduced(self, obj_id=None, list_name=None, group_id=None, featurewise=None, **reducer_args):
        _used_default_group = False
        if group_id is None:
            group_id = self._default_group_id
            _used_default_group = True

        _used_default_list = False
        if list_name is None:
            list_name = self._default_list_id
            _used_default_list = True

        _used_default_featurewise = False
        if featurewise is None:
            featurewise = self._default_featurewise
            _used_default_featurewise = True

        if obj_id is None:
            if self._last_reducer_accessed is None or \
                    (not _used_default_list or not _used_default_group or not _used_default_featurewise):
                #if last_reducer_accessed hasn't been set or if the user asks for specific params,
                #else return the last reducer gotten by this method

                obj_id = list_name + ":" + group_id + ":" + str(featurewise)

            else:
                obj_id = self._last_reducer_accessed

        self._last_reducer_accessed = obj_id
        if featurewise:
            rdc_dict = self.featurewise_reduction
        else:
            rdc_dict = self.samplewise_reduction
        try:
            return rdc_dict[obj_id]
        except:
            rdc_obj = self.make_reduced(list_name, group_id, featurewise=featurewise, **reducer_args)
            rdc_obj.obj_id = obj_id
            rdc_dict[obj_id] = rdc_obj

        return rdc_dict[obj_id]

    def get_classifier(self, gene_list_name=None, sample_list_name=None, clf_var=None,
                      obj_id=None,
                      **classifier_args):
        """
        list_name = list of features to use for this clf
        obj_id = name of this classifier
        clf_var = boolean or categorical pd.Series
        """

        _used_default_group = False
        if sample_list_name is None:
            sample_list_name = self._default_group_id
            _used_default_group = True

        _used_default_list = False
        if gene_list_name is None:
            gene_list_name = self._default_list_id
            _used_default_list = True

        if obj_id is None:
            if self._last_predictor_accessed is None or \
                    (not _used_default_list or not _used_default_group):
                #if last_reducer_accessed hasn't been set or if the user asks for specific params,
                #else return the last reducer gotten by this method

                obj_id = gene_list_name + ":" + sample_list_name + ":" + clf_var
            else:
                obj_id = self._last_predictor_accessed

        self._last_predictor_accessed = obj_id
        #print "I am a %s" % type(self)
        #print "here are my clf_dict keys: %s" % " ".join(self.clf_dict.keys())
        try:
            return self.clf_dict[obj_id]
        except:
            clf = self.make_classifier(gene_list_name, sample_list_name, clf_var, **classifier_args)
            clf.obj_id = obj_id
            self.clf_dict[obj_id] = clf

        return self.clf_dict[obj_id]

    def get_min_samples(self):
        if hasattr(self, 'min_samples'):
            return self.min_samples
        else:
            return 12
        return self

    def set_min_samples(self, min_samples):

        self.min_samples = min_samples
        return self

    def twoway(self, sample1, sample2, **kwargs):
        from .._submaraine_viz import TwoWayScatterViz
        pCut = kwargs['pCut']
        this_name = "_".join([sample1, sample2, str(pCut)])
        if this_name in self.localZ_dict:
            vz = self.localZ_dict[this_name]
        else:
            df = self.df
            df.rename_axis(self.get_naming_fun(), 1)
            vz = TwoWayScatterViz(sample1, sample2, df, **kwargs)
            self.localZ_dict[this_name] = vz

        return vz

    def plot_twoway(self, sample1, sample2, **kwargs):
        vz = self.twoway(sample1, sample2, **kwargs)
        vz()
        return vz