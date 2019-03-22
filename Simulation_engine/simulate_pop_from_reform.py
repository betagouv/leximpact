# -*- coding: utf-8 -*-


from typing import Callable

import pandas
import time

from openfisca_core.simulation_builder import SimulationBuilder
from openfisca_france import FranceTaxBenefitSystem
from openfisca_core import periods
from openfisca_france.model.base import Reform

TBS = FranceTaxBenefitSystem()


def fread(filename: str) -> Callable:
    if filename[-3:] == ".h5":
        fun = pandas.read_hdf

    else:
        fun = pandas.read_csv

    return lambda path: fun(path.format(filename))


def load_data(fread: Callable):
    try:
        data = fread("./{}")

    except(Exception):
        try:
            data = fread("./Simulation_engine/{}")

        except(Exception):
            data = fread("C:/EIG/Leximpact_git/Simulation_engine/{}")

    return data


def reform_from_bareme(tbs, taux, period):
    class apply_reform(Reform):
        def apply(self):
            self.modify_parameters(modifier_function = reform)

    def reform(parameters):
        instant = periods.instant(period)

        print("bareme avant modif :")
        print(parameters.impot_revenu.bareme.get_at_instant(instant))

        seuil = parameters.impot_revenu.bareme.get_at_instant(instant)
        reform_period = periods.period("year:1900:200")  # Pour le moment mes réformes sont sur l'éternité

        for i in range(len(seuil.rates)):
            parameters.impot_revenu.bareme.brackets[i].threshold.update(
                period = reform_period,
                value = seuil.thresholds[i] if i != 1 else min(taux, seuil.thresholds[i + 1])
                )

            parameters.impot_revenu.bareme.brackets[i].rate.update(period = reform_period, value = seuil.rates[i])

        for i in range(len(seuil.rates), 15):
            try:
                parameters.impot_revenu.bareme.brackets[i].threshold.update(
                    period = reform_period,
                    value = seuil.thresholds[-1] + i
                    )

                parameters.impot_revenu.bareme.brackets[i].rate.update(period = reform_period, value = seuil.rates[-1])

            except(Exception):
                pass

        parameters.impot_revenu.bareme.brackets[1].threshold.update(period = reform_period, value = taux)

        print("bareme après modif :")
        print(parameters.impot_revenu.bareme.get_at_instant(instant))

        return parameters

    return apply_reform(tbs)


def simulation(tbs, data, timer = None):
    if timer:
        starttime = timer.time()
        print("Elapsed time : {:.2f}".format(time.time() - starttime))

    # Traduction des roles attribués au format openfisca
    data["quimenof"] = "enfant"
    data.loc[data["quifoy"] == 1, 'quimenof'] = "conjoint"
    data.loc[data["quifoy"] == 0, 'quimenof'] = "personne_de_reference"

    data["quifoyof"] = "personne_a_charge"
    data.loc[data["quifoy"] == 1, 'quifoyof'] = "conjoint"
    data.loc[data["quifoy"] == 0, 'quifoyof'] = "declarant_principal"

    data["quifamof"] = "enfant"
    data.loc[data["quifam"] == 1, 'quifamof'] = "conjoint"
    data.loc[data["quifam"] == 0, 'quifamof'] = "demandeur"

    sb = SimulationBuilder()
    sb.create_entities(tbs)

    sb.declare_person_entity('individu', data.index)

    # Creates openfisca entities and generates grouped

    listentities = {
        "foy": "foyer_fiscal",
        "men": "menage",
        "fam": "famille",
        }

    instances = {}
    dictionnaire_datagrouped = {"individu": data}

    for ent, ofent in listentities.items():
        persons_ent = data["id" + ent].values
        persons_ent_roles = data["qui" + ent + "of"].values
        ent_ids = data["id" + ent].unique()
        instances[ofent] = sb.declare_entity(ofent, ent_ids)
        sb.join_with_persons(instances[ofent], persons_ent, roles = persons_ent_roles)

        # The following ssumes data defined for an entity are the same for all rows in the same entity
        # Or at least that the first non null value found for an entity will always be the total value for an entity
        # (Which is the case for f4ba). These checks are performed in the checkdata function defined belowx
        dictionnaire_datagrouped[ofent] = data.groupby("id" + ent, as_index = False).first().sort_values(by = "id" + ent)

    # These variables should not be attributed to any OpenFisca Entity
    columns_not_OF_variables = set([
        "idmen",
        "idfoy",
        "idfam",
        "noindiv",
        "level_0",
        "quifam",
        "quifoy",
        "quimen",
        "wprm",
        "index",
        "idmen_original",
        "idfoy_original",
        "idfam_original",
        "quifamof",
        "quifoyof",
        "quimenof",
        ])

    simulation = sb.build(tbs)

    # Attribution des variables à la bonne entité OpenFisca
    for colonne in data.columns:
        if colonne not in columns_not_OF_variables:
            try:
                simulation.set_input(colonne, period, dictionnaire_datagrouped[tbs.get_variable(colonne).entity.key][colonne])
                print("{} was attributed to {}".format(colonne, tbs.get_variable(colonne).entity.key))

            except(Exception):
                print("{} failed to be attributed to {}".format(colonne, tbs.get_variable(colonne).entity.key))
                raise

    if timer:
        print("Elapsed time : {:.2f}".format(timer.time() - starttime))

    return simulation, dictionnaire_datagrouped


def compare(taux: int, period: str, simulation_base, simulation_reform):
    res = []

    for simulation, dictionnaire_datagrouped in [simulation_base, simulation_reform]:
        for nomvariable in ["irpp", "nbptr"]:
            st = time.time()
            dictionnaire_datagrouped["foyer_fiscal"][nomvariable] = simulation.calculate(nomvariable, period, max_nb_cycles = 1)
            dictionnaire_datagrouped["foyer_fiscal"][nomvariable + "w"] = dictionnaire_datagrouped["foyer_fiscal"][nomvariable] * dictionnaire_datagrouped["foyer_fiscal"]["wprm"]

            print("{} sum : {}  mean : {}".format(nomvariable, dictionnaire_datagrouped["foyer_fiscal"][nomvariable + "w"].sum(), dictionnaire_datagrouped["foyer_fiscal"][nomvariable + "w"].sum() / dictionnaire_datagrouped["foyer_fiscal"]["wprm"].sum()))
            print("Elapsed : {:.2f}".format(time.time() - st))

            if nomvariable == "irpp":
                res += [-dictionnaire_datagrouped["foyer_fiscal"][nomvariable + "w"].sum() / dictionnaire_datagrouped["foyer_fiscal"]["wprm"].sum()]

    print("Je suis Wengerboy et j'ai été lancé avec un parametre de {} et oui j'ai fini {}".format(taux, res))

    return res


if __name__ == "__main__":
    data = load_data(fread("dummy_data.h5"))
    taux = 9500
    period = "2014"
    reform = reform_from_bareme(TBS, taux, period)
    simulation_base = simulation(TBS, data, timer = time)
    simulation_reform = simulation(reform, data, timer = time)
    compare(taux, period, simulation_base, simulation_reform)
