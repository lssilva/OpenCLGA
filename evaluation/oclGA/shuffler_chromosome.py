import numpy
import pyopencl as cl

from simple_gene import SimpleGene

class ShufflerChromosome:
    kernel_file = "shuffler_chromosome.c"

    populate_function = "shuffler_chromosome_populate"
    struct_name = "__ShufflerChromosome"
    chromosome_size_define = "SHUFFLER_CHROMOSOME_GENE_SIZE"

    # ShufflerChromosome - a chromosome contains a list of Genes.
    # __genes - an ordered list of Genes
    # __name - name of the chromosome
    # dna - an listed of Gene's dna
    # dna_total_length - sum of the lenght of all genes's dna
    def __init__(self, genes, name=""):
        assert all(isinstance(gene, SimpleGene) for gene in genes)
        assert type(genes) == list
        self.__genes = genes
        self.__name = name

    @property
    def num_of_genes(self):
        return len(self.__genes)

    @property
    def name(self):
        return self.__name

    @property
    def dna_total_length(self):
        return self.num_of_genes

    @property
    def dna(self):
        return [gene.dna for gene in self.__genes]

    @dna.setter
    def dna(self, dna):
        assert self.num_of_genes == len(dna)
        for i, gene in enumerate(self.__genes):
            gene.dna = dna[i]

    @property
    def genes(self):
        return self.__genes

    @property
    def gene_elements(self):
        return [] if len(self.__genes) == 0 else self.__genes[0].elements

    @property
    def gene_elements_in_kernel(self):
        return [] if len(self.__genes) == 0 else self.__genes[0].elements_in_kernel

    def kernelize(self):
        candidates = self.__genes[0].kernelize()
        defines = "#define SHUFFLER_CHROMOSOME_GENE_SIZE " + str(self.num_of_genes) + "\n"
        typedef = "typedef struct {\n" +\
                  "  int genes[" + str(self.num_of_genes) + "];\n" +\
                  "} __ShufflerChromosome;\n"
        return candidates + defines + typedef

    def preexecute_kernels(self, ctx, queue, population):
        ## initialize global variables for kernel execution
        total_dna_size = population * self.dna_total_length

        other_chromosomes = numpy.zeros(total_dna_size, dtype=numpy.int32)
        cross_map = numpy.zeros(total_dna_size, dtype=numpy.int32)
        ratios = numpy.zeros(population, dtype=numpy.float32)
        best_fit = [0]
        weakest_fit = [0]

        mf = cl.mem_flags

        self.__dev_ratios = cl.Buffer(ctx, mf.WRITE_ONLY, ratios.nbytes)
        self.__dev_best = cl.Buffer(ctx, mf.READ_WRITE | mf.COPY_HOST_PTR,
                                    hostbuf=numpy.array(best_fit, dtype=numpy.float32))
        self.__dev_weakest = cl.Buffer(ctx, mf.READ_WRITE | mf.COPY_HOST_PTR,
                                       hostbuf=numpy.array(weakest_fit, dtype=numpy.float32))
        self.__dev_other_chromosomes = cl.Buffer(ctx, mf.READ_WRITE | mf.COPY_HOST_PTR,
                                                 hostbuf=other_chromosomes)
        self.__dev_cross_map = cl.Buffer(ctx, mf.READ_WRITE | mf.COPY_HOST_PTR,
                                         hostbuf=cross_map)

    def execute_crossover(self, prg, queue, population, generation_idx, prob_crossover,
                          dev_chromosomes, dev_fitnesses, dev_rnum, wait_for=None):
        prg.shuffler_chromosome_calc_ratio(queue,
                                           (1,),
                                           (1,),
                                           dev_fitnesses,
                                           self.__dev_ratios,
                                           self.__dev_best,
                                           self.__dev_weakest).wait()
        prg.shuffler_chromosome_pick_chromosomes(queue,
                                                 (population,),
                                                 (population,),
                                                 dev_chromosomes,
                                                 dev_fitnesses,
                                                 self.__dev_other_chromosomes,
                                                 self.__dev_ratios,
                                                 dev_rnum).wait()
        prg.shuffler_chromosome_do_crossover(queue,
                                             (population,),
                                             (population,),
                                             dev_chromosomes,
                                             dev_fitnesses,
                                             self.__dev_other_chromosomes,
                                             self.__dev_cross_map,
                                             self.__dev_best,
                                             numpy.float32(prob_crossover),
                                             dev_rnum).wait()


    def execute_mutation(self, prg, queue, population, generation_idx, prob_mutate,
                         dev_chromosomes, dev_fitnesses, dev_rnum, wait_for=None):
        prg.shuffler_chromosome_single_gene_mutate(queue,
                                                   (population,),
                                                   (population,),
                                                   dev_chromosomes,
                                                   numpy.float32(prob_mutate),
                                                   dev_rnum).wait()