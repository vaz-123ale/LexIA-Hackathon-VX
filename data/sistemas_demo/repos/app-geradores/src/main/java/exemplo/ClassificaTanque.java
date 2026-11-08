package exemplo;

// Classificação de tanques de consumo de grupos geradores (sistema fictício de demonstração)
public class ClassificaTanque {
    public static String classificar(Tanque t) {
        if (t.integradoAoGerador()) {
            return "ANEXO_III_ITEM_2_1_INTEGRADO";
        }
        return "ANEXO_III_ITEM_2_1_SEPARADO";
    }
}
